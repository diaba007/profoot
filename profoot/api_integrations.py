# profoot/api_integrations.py

import requests
import os
import logging
from django.conf import settings
from django.utils import timezone
from datetime import timedelta, datetime  # Assurez-vous que datetime est importé

# Assurez-vous que Match est bien importé
from .models import Pronostic, Match

# Initialisation du logger
logger = logging.getLogger( __name__ )

# --- Configuration Sportmonks API ---
SPORTMONKS_API_TOKEN = os.environ.get( 'SPORTMONKS_API_TOKEN' )
SPORTMONKS_BASE_URL = "https://api.sportmonks.com/v3/football"

if not SPORTMONKS_API_TOKEN:
    logger.error( "SPORTMONKS_API_TOKEN non trouvé. Veuillez le définir comme variable d'environnement." )


def _make_sportmonks_request(endpoint, params=None):
    """
    Fonction interne générique pour faire des requêtes à l'API Sportmonks.
    Gère l'authentification et les erreurs de base.
    Retourne la réponse JSON complète ou None en cas d'erreur.
    """
    if not SPORTMONKS_API_TOKEN:
        logger.error( f"Requête API Sportmonks échouée pour l'endpoint {endpoint}: Clé API manquante." )
        return None

    full_url = f"{SPORTMONKS_BASE_URL}/{endpoint}"

    all_params = {'api_token': SPORTMONKS_API_TOKEN}
    if params:
        all_params.update( params )

    try:
        response = requests.get( full_url, params=all_params, timeout=10 )
        response.raise_for_status()
        data = response.json()
        return data  # Retourne la réponse JSON complète
    except requests.exceptions.HTTPError as e:
        logger.error(
            f"Erreur HTTP lors de l'appel à Sportmonks ({full_url}) : {e.response.status_code} - {e.response.text}" )
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error( f"Erreur de connexion à Sportmonks ({full_url}) : {e}" )
        return None
    except requests.exceptions.Timeout as e:
        logger.error( f"Délai d'attente expiré lors de l'appel à Sportmonks ({full_url}) : {e}" )
        return None
    except requests.exceptions.RequestException as e:
        logger.error( f"Erreur inattendue lors de l'appel à Sportmonks ({full_url}) : {e}" )
        return None
    except Exception as e:
        logger.error( f"Erreur générale lors du traitement de la requête Sportmonks ({full_url}) : {e}" )
        return None


def fetch_match_data_from_api(event_id):
    """
    Récupère les données d'un match spécifique (détaillées) depuis l'API Sportmonks.
    Nous ne passons AUCUN include ici, car l'API semble les rejeter constamment.
    Retourne un dictionnaire avec les données du match ou None en cas d'erreur.
    """
    full_response = _make_sportmonks_request( f'fixtures/{event_id}' )  # <--- AUCUN PARAMÈTRE 'include' ICI
    if full_response:
        return full_response.get( 'data' )
    return None


def fetch_league_name_from_api(league_id):
    """
    Récupère le nom d'une ligue à partir de son ID.
    """
    if not league_id:
        return "N/A"
    full_response = _make_sportmonks_request( f'leagues/{league_id}' )  # <--- AUCUN PARAMÈTRE 'include' ICI
    if full_response and full_response.get( 'data' ):
        return full_response['data'].get( 'name', 'N/A' )
    return "N/A"


def fetch_venue_name_from_api(venue_id):
    """
    Récupère le nom d'un stade à partir de son ID.
    """
    if not venue_id:
        return "N/A"
    full_response = _make_sportmonks_request( f'venues/{venue_id}' )  # <--- AUCUN PARAMÈTRE 'include' ICI
    if full_response and full_response.get( 'data' ):
        return full_response['data'].get( 'name', 'N/A' )
    return "N/A"


def update_pronostic_from_api_data(pronostic: Pronostic):
    """
    Met à jour un objet Pronostic avec les données de score et de statut
    récupérées de l'API Sportmonks.
    """
    if not pronostic.match:
        logger.warning( f"Le pronostic ID {pronostic.pk} n'a pas de match associé. Impossible de mettre à jour." )
        return False

    match_data = fetch_match_data_from_api( pronostic.match.api_event_id )

    if not match_data:
        logger.warning(
            f"Aucune donnée trouvée de Sportmonks pour l'ID d'événement API {pronostic.match.api_event_id}." )
        return False

    is_finished = match_data.get( 'finished' )
    sportmonks_status_id = match_data.get( 'state_id' )

    FINAL_STATE_IDS = [3, 4, 5]
    CANCELLED_STATE_IDS = [6, 7, 8, 9, 10]

    if not is_finished and sportmonks_status_id not in CANCELLED_STATE_IDS:
        logger.info(
            f"Le match ID {pronostic.match.api_event_id} n'est pas terminé ou son statut est incertain (Sportmonks state_id: {sportmonks_status_id})." )
        return False

    scores_data = match_data.get( 'scores', {} )
    fulltime_scores = scores_data.get( 'fulltime', {} )
    home_score = fulltime_scores.get( 'home' )
    away_score = fulltime_scores.get( 'away' )

    if home_score is None or away_score is None:
        logger.warning(
            f"Scores finaux non disponibles de Sportmonks pour l'ID d'événement API {pronostic.match.api_event_id}." )
        return False

    pronostic.match.score_final_domicile = home_score
    pronostic.match.score_final_exterieur = away_score
    status_api_name = match_data.get( 'state', {} ).get( 'name' )
    status_api_id = match_data.get( 'state_id' )
    pronostic.match.status_api = status_api_name or str( status_api_id )
    pronostic.match.save()

    new_resultat = pronostic.resultat

    if sportmonks_status_id in CANCELLED_STATE_IDS:
        new_resultat = 'ANNULE'
    else:
        total_goals = home_score + away_score

        if pronostic.type_pari == '1N2':
            if home_score > away_score:
                real_outcome = '1'
            elif away_score > home_score:
                real_outcome = '2'
            else:
                real_outcome = 'N'

            if real_outcome in pronostic.prediction_details.upper():
                new_resultat = 'GAGNANT'
            else:
                new_resultat = 'PERDANT'

        elif pronostic.type_pari == 'OVER_UNDER':
            try:
                parts = pronostic.prediction_details.split( ' ' )
                if len( parts ) >= 2:
                    direction = parts[0].strip().upper()
                    line = float( parts[1].strip() )

                    if direction == 'OVER':
                        if total_goals > line:
                            new_resultat = 'GAGNANT'
                        else:
                            new_resultat = 'PERDANT'
                    elif direction == 'UNDER':
                        if total_goals < line:
                            new_resultat = 'GAGNANT'
                        else:
                            new_resultat = 'PERDANT'
                    else:
                        logger.warning(
                            f"Type OVER_UNDER mal formaté pour le pronostic {pronostic.pk}: {pronostic.prediction_details}" )
                        new_resultat = pronostic.resultat
                else:
                    logger.warning(
                        f"Format de prédiction OVER_UNDER insuffisant pour le pronostic {pronostic.pk}: {pronostic.prediction_details}" )
                    new_resultat = pronostic.resultat
            except (ValueError, IndexError):
                logger.error(
                    f"Impossible de parser la ligne OVER_UNDER pour le pronostic {pronostic.pk}: {pronostic.prediction_details}" )
                new_resultat = pronostic.resultat

        elif pronostic.type_pari == 'BUTEUR':
            logger.info(
                f"Le type de pari 'BUTEUR' pour le pronostic {pronostic.pk} nécessite une vérification manuelle ou une logique API plus complexe." )
            new_resultat = pronostic.resultat

        elif pronostic.type_pari == 'HANDICAP':
            try:
                if 'handicap' in pronostic.prediction_details.lower():
                    if pronostic.equipe_domicile in pronostic.prediction_details and '-' in pronostic.prediction_details:
                        handicap_val = float( pronostic.prediction_details.split( '-' )[1].split( ' ' )[0] )
                        if (home_score - handicap_val) > away_score:
                            new_resultat = 'GAGNANT'
                        else:
                            new_resultat = 'PERDANT'
                    elif pronostic.equipe_exterieur in pronostic.prediction_details and '-' in pronostic.prediction_details:
                        handicap_val = float( pronostic.prediction_details.split( '-' )[1].split( ' ' )[0] )
                        if (away_score - handicap_val) > home_score:
                            new_resultat = 'GAGNANT'
                        else:
                            new_resultat = 'PERDANT'
                    elif pronostic.equipe_domicile in pronostic.prediction_details and '+' in pronostic.prediction_details:
                        handicap_val = float( pronostic.prediction_details.split( '+' )[1].split( ' ' )[0] )
                        if (home_score + handicap_val) > away_score:
                            new_resultat = 'GAGNANT'
                        else:
                            new_resultat = 'PERDANT'
                    elif pronostic.equipe_exterieur in pronostic.prediction_details and '+' in pronostic.prediction_details:
                        handicap_val = float( pronostic.prediction_details.split( '+' )[1].split( ' ' )[0] )
                        if (away_score + handicap_val) > home_score:
                            new_resultat = 'GAGNANT'
                        else:
                            new_resultat = 'PERDANT'
                    else:
                        logger.warning(
                            f"Format de prédiction HANDICAP inconnu pour le pronostic {pronostic.pk}: {pronostic.prediction_details}" )
                        new_resultat = pronostic.resultat
                else:
                    logger.warning(
                        f"Le type de pari 'HANDICAP' pour le pronostic {pronostic.pk} est mal formaté ou non géré automatiquement." )
                    new_resultat = pronostic.resultat
            except (ValueError, IndexError):
                logger.error(
                    f"Erreur de parsing HANDICAP pour le pronostic {pronostic.pk}: {pronostic.prediction_details}" )
                new_resultat = pronostic.resultat

        elif pronostic.type_pari == 'DOUBLE_CHANCE':
            if "1N" in pronostic.prediction_details.upper():
                if home_score >= away_score:
                    new_resultat = 'GAGNANT'
                else:
                    new_resultat = 'PERDANT'
            elif "12" in pronostic.prediction_details.upper():
                if home_score != away_score:
                    new_resultat = 'GAGNANT'
                else:
                    new_resultat = 'PERDANT'
            elif "N2" in pronostic.prediction_details.upper():
                if away_score >= home_score:
                    new_resultat = 'GAGNANT'
                else:
                    new_resultat = 'PERDANT'
            else:
                logger.warning(
                    f"Format de prédiction DOUBLE_CHANCE inconnu pour le pronostic {pronostic.pk}: {pronostic.prediction_details}" )
                new_resultat = pronostic.resultat

    if new_resultat != pronostic.resultat:
        pronostic.resultat = new_resultat
        pronostic.save()
        logger.info(
            f"Pronostic ID {pronostic.pk} mis à jour : Statut -> {pronostic.get_resultat_display()}, Score -> {pronostic.match.score_final_domicile}-{pronostic.match.score_final_exterieur}" )
        return True
    else:
        logger.info(
            f"Pronostic ID {pronostic.pk} : Pas de changement de statut nécessaire ou le statut est déjà final." )
        return False


def fetch_and_store_upcoming_matches(days_in_advance=7):
    """
    Récupère les matchs à venir depuis l'API Sportmonks pour les jours spécifiés
    et les stocke/met à jour dans le modèle Match.
    Retourne le nombre de matchs ajoutés et mis à jour.
    """
    added_count = 0
    updated_count = 0

    start_date = timezone.now().date()
    end_date = start_date + timedelta( days=days_in_advance )

    logger.info( f"Récupération des matchs Sportmonks entre {start_date} et {end_date}..." )

    url_endpoint = f"fixtures/between/{start_date.isoformat()}/{end_date.isoformat()}"
    params = {
        "page": 1,
        # AUCUN INCLUDE ICI pour la liste, car 'fixtures/between' ne les supporte pas.
    }

    while True:
        # Première étape : Récupérer la liste de base des fixtures (sans includes détaillés)
        full_api_response_list = _make_sportmonks_request( url_endpoint, params=params )

        if not full_api_response_list:
            logger.warning(
                f"Aucune réponse API reçue pour la page {params['page']} de l'endpoint de liste. Cela peut indiquer une erreur ou la fin des pages." )
            break

        fixtures_list_data = full_api_response_list.get( 'data' )
        meta_list = full_api_response_list.get( 'meta', {} )

        if not fixtures_list_data:
            logger.warning(
                f"Aucun match trouvé dans la réponse API de liste pour la page {params['page']}. Fin de la récupération." )
            break

        for basic_fixture_info in fixtures_list_data:
            fixture_id = basic_fixture_info.get( 'id' )
            if not fixture_id:
                logger.warning( f"Fixture sans ID trouvée. Ignorée : {basic_fixture_info}" )
                continue

            # Deuxième étape : Récupérer les détails complets de chaque fixture
            # Cette fonction 'fetch_match_data_from_api' n'a plus d'includes
            detailed_fixture = fetch_match_data_from_api( fixture_id )

            if not detailed_fixture:
                logger.warning( f"Impossible de récupérer les détails pour la fixture ID {fixture_id}. Ignorée." )
                continue

            # --- AJOUT DU LOG DE DÉBOGAGE ICI ---
            # Cela imprimera la structure JSON de chaque fixture détaillée
            logger.debug( f"Traitement de la fixture détaillée: {detailed_fixture}" )

            try:
                sportmonks_id = detailed_fixture.get( 'id' )
                date_match_str = detailed_fixture.get( 'starting_at' )

                # Correction : Rendre la date et l'heure timezone-aware
                try:
                    # Tente de parser avec le format exact de votre exemple "YYYY-MM-DD HH:MM:SS"
                    naive_datetime = datetime.strptime( date_match_str, "%Y-%m-%d %H:%M:%S" )
                    date_match = timezone.make_aware( naive_datetime, timezone.get_current_timezone() )
                except ValueError:
                    # Si le format n'est pas le même (ex: contient 'Z' ou décalage), tente fromisoformat
                    date_match = timezone.make_aware(
                        datetime.fromisoformat( date_match_str.replace( 'Z', '+00:00' ) ) )

                home_team_name = "N/A"
                away_team_name = "N/A"
                league_name = "N/A"
                stadium_name = "N/A"

                # --- EXTRACTION DES DONNÉES BASÉE SUR VOTRE EXEMPLE JSON ---
                # Noms des équipes : extraire de la chaîne 'name'
                fixture_name = detailed_fixture.get( 'name', '' )
                if ' vs ' in fixture_name:
                    parts = fixture_name.split( ' vs ' )
                    if len( parts ) == 2:
                        home_team_name = parts[0].strip()
                        away_team_name = parts[1].strip()
                else:
                    home_team_name = fixture_name  # Fallback si pas de 'vs'
                    logger.warning( f"Format de nom de fixture inattendu pour ID {sportmonks_id}: {fixture_name}" )

                # Nom de la ligue : faire un appel API séparé
                league_id = detailed_fixture.get( 'league_id' )
                league_name = fetch_league_name_from_api( league_id )

                # Nom du stade : faire un appel API séparé
                venue_id = detailed_fixture.get( 'venue_id' )
                stadium_name = fetch_venue_name_from_api( venue_id )

                scores_data = detailed_fixture.get( 'scores', {} )
                fulltime_scores = scores_data.get( 'fulltime', {} )
                score_final_domicile = fulltime_scores.get( 'home' )
                score_final_exterieur = fulltime_scores.get( 'away' )

                status_api_name = detailed_fixture.get( 'state', {} ).get( 'name' )
                status_api_id = detailed_fixture.get( 'state_id' )
                status_api = status_api_name or str( status_api_id )

                match, created = Match.objects.update_or_create(  # CORRECTION APPLIQUÉE
                    api_event_id=sportmonks_id,
                    defaults={
                        'discipline': 'FOOTBALL',
                        'equipe_domicile': home_team_name,
                        'equipe_exterieur': away_team_name,
                        'date_match': date_match,
                        'ligue': league_name,
                        'stade': stadium_name,
                        'score_final_domicile': score_final_domicile,
                        'score_final_exterieur': score_final_exterieur,
                        'status_api': status_api,
                    }
                )

                if created:
                    added_count += 1
                    logger.info( f"Match ajouté : {home_team_name} vs {away_team_name} ({league_name})" )
                else:
                    updated_count += 1
                    logger.info( f"Match mis à jour : {home_team_name} vs {away_team_name} ({league_name})" )

            except Exception as e:
                logger.error( f"Erreur lors du traitement d'une fixture Sportmonks (ID: {fixture_id}): {e}",
                              exc_info=True )

        # Gérer la pagination pour la liste initiale des fixtures
        if 'pagination' in meta_list:
            pagination_info = meta_list['pagination']
            current_page = pagination_info.get( 'current_page' )
            last_page = pagination_info.get( 'last_page' )

            if current_page < last_page:
                params['page'] = current_page + 1
                logger.info( f"Passage à la page suivante de la liste: {params['page']}/{last_page}" )
            else:
                break
        else:
            break

    return added_count, updated_count

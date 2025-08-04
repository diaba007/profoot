import requests
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.http import Http404
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from datetime import datetime, time  # Ensure datetime is imported
from django.contrib.auth import authenticate, login, logout
import os
import logging
from django.utils import timezone  # Importez timezone ici aussi

# Importez les fonctions d'intégration API nécessaires
from .api_integrations import _make_sportmonks_request, fetch_league_name_from_api, fetch_venue_name_from_api

# Import all necessary models and forms
from .models import Pronostic, Follow, Notification, Comment, UserProfile, BookmakerOffer, Match
from .forms import CustomUserCreationForm, PronosticForm, CommentForm

# --- Configuration Sportmonks API ---
SPORTMONKS_API_TOKEN = os.environ.get( 'SPORTMONKS_API_TOKEN' )
SPORTMONKS_BASE_URL = "https://api.sportmonks.com/v3/football"

# Initialisation du logger pour les vues
logger = logging.getLogger( __name__ )


def get_event_details_from_sportmonks(event_id):
    """
    Récupère les détails d'un match spécifique depuis l'API Sportmonks.
    Cette fonction ne passe AUCUN include, car l'API semble les rejeter.
    Retourne un dictionnaire avec les données du match formatées pour le formulaire ou None en cas d'erreur.
    """
    if not SPORTMONKS_API_TOKEN:
        logger.error( "Impossible de récupérer les détails de l'événement Sportmonks : Clé API manquante." )
        return None

    # Utilisation de _make_sportmonks_request sans paramètres 'include'
    full_response = _make_sportmonks_request( f'fixtures/{event_id}' )

    if not full_response or not full_response.get( 'data' ):
        logger.warning( f"API Sportmonks: Aucun résultat trouvé pour l'ID {event_id}. Réponse: {full_response}" )
        return None

    fixture = full_response['data']

    # Extraction des noms d'équipes à partir du champ 'name'
    home_team_name = "N/A"
    away_team_name = "N/A"
    fixture_name = fixture.get( 'name', '' )
    if ' vs ' in fixture_name:
        parts = fixture_name.split( ' vs ' )
        if len( parts ) == 2:
            home_team_name = parts[0].strip()
            away_team_name = parts[1].strip()
    else:
        home_team_name = fixture_name  # Fallback si pas de 'vs'
        logger.warning( f"Format de nom de fixture inattendu pour ID {fixture.get( 'id' )}: {fixture_name}" )

    # Récupération du nom de la ligue via un appel séparé
    league_id = fixture.get( 'league_id' )
    league_name = fetch_league_name_from_api( league_id )

    # Récupération du nom du stade via un appel séparé
    venue_id = fixture.get( 'venue_id' )
    stadium_name = fetch_venue_name_from_api( venue_id )

    event_datetime_str = fixture.get( 'starting_at' )
    event_datetime_obj = None
    if event_datetime_str:
        try:
            # Tente de parser avec le format exact de votre exemple "YYYY-MM-DD HH:MM:SS"
            naive_datetime = datetime.strptime( event_datetime_str, "%Y-%m-%d %H:%M:%S" )
            # CORRECTION ICI : Rendre la date et l'heure timezone-aware
            event_datetime_obj = timezone.make_aware( naive_datetime, timezone.get_current_timezone() )
        except ValueError:
            # Si le format n'est pas le même (ex: contient 'Z' ou décalage), tente fromisoformat
            try:
                # CORRECTION ICI : Rendre la date et l'heure timezone-aware
                event_datetime_obj = timezone.make_aware(
                    datetime.fromisoformat( event_datetime_str.replace( 'Z', '+00:00' ) ) )
            except ValueError:
                logger.warning( f"Erreur de format de date Sportmonks pour {event_datetime_str} (ID: {event_id})" )
                pass

    # Scores finaux (si le match est terminé) - souvent directement sur l'objet fixture
    scores_data = fixture.get( 'scores', {} )
    fulltime_scores = scores_data.get( 'fulltime', {} )
    score_final_domicile = fulltime_scores.get( 'home' )
    score_final_exterieur = fulltime_scores.get( 'away' )

    # Statut du match (Sportmonks utilise 'state_id' ou 'finished' booléen)
    status_event = "N/A"
    if fixture.get( 'finished' ):
        status_event = "Terminé"
    elif fixture.get( 'state_id' ) == 1:
        status_event = "À venir"
    elif fixture.get( 'state_id' ) == 2:
        status_event = "En direct"
    elif fixture.get( 'state', {} ).get( 'name' ):  # Tente d'obtenir le nom de l'état
        status_event = fixture.get( 'state', {} ).get( 'name' )
    elif fixture.get( 'state_id' ):  # Fallback à l'ID si pas de nom
        status_event = str( fixture.get( 'state_id' ) )

    return {
        'api_event_id': fixture.get( 'id' ),  # L'ID Sportmonks
        'discipline': 'FOOTBALL',  # Assumé, à modifier si l'API le fournit
        'equipe_domicile': home_team_name,
        'equipe_exterieur': away_team_name,
        'ligue': league_name,
        'date_match': event_datetime_obj.date() if event_datetime_obj else None,
        'heure_match': event_datetime_obj.time() if event_datetime_obj else None,
        'score_final_domicile': score_final_domicile,
        'score_final_exterieur': score_final_exterieur,
        'status_event': status_event,
        'event_name': f"{home_team_name} vs {away_team_name}",
        'stade': stadium_name,
    }


def get_base_context(request):
    unread_notifications_count = 0
    if request.user.is_authenticated:
        profile, created = UserProfile.objects.get_or_create( user=request.user )
        unread_notifications_count = request.user.notifications.filter( is_read=False ).count()
    return {
        'unread_notifications_count': unread_notifications_count
    }


def liste_pronostics(request):
    pronostics = Pronostic.objects.all()

    sort_by = request.GET.get( 'sort', '-date_match' )
    if sort_by == 'date_asc':
        pronostics = pronostics.order_by( 'date_match' )
    else:
        pronostics = pronostics.order_by( '-date_match' )

    filter_status = request.GET.get( 'status' )
    if filter_status and filter_status in [choice[0] for choice in Pronostic.STATUT_CHOICES]:
        pronostics = pronostics.filter( resultat=filter_status )

    filter_discipline = request.GET.get( 'discipline' )
    if filter_discipline and filter_discipline in [choice[0] for choice in Pronostic.DISCIPLINE_CHOICES]:
        pronostics = pronostics.filter( discipline=filter_discipline )

    query = request.GET.get( 'q' )
    if query:
        pronostics = pronostics.filter(
            Q( equipe_domicile__icontains=query ) |
            Q( equipe_exterieur__icontains=query ) |
            Q( ligue__icontains=query ) |
            Q( prediction_details__icontains=query )
        ).distinct()

    paginator = Paginator( pronostics, 5 )
    page_number = request.GET.get( 'page' )
    page_obj = paginator.get_page( page_number )

    if not request.session.get( 'welcome_message_shown' ):
        messages.info( request, "Bienvenue sur ProFoot Pronos ! Découvrez nos dernières analyses de matchs." )
        request.session['welcome_message_shown'] = True

    context = get_base_context( request )
    context.update( {
        'page_obj': page_obj,
        'current_sort': sort_by,
        'current_status': filter_status,
        'search_query': query,
        'status_choices': Pronostic.STATUT_CHOICES,
        'discipline_choices': Pronostic.DISCIPLINE_CHOICES,
        'current_discipline': filter_discipline,
    } )
    return render( request, 'profoot/liste_pronostics.html', context )


def detail_pronostic(request, pk):
    pronostic = get_object_or_404( Pronostic, pk=pk )
    comments = pronostic.comments.all()

    if request.method == 'POST':
        comment_form = CommentForm( request.POST )
        if request.user.is_authenticated:
            if comment_form.is_valid():
                new_comment = comment_form.save( commit=False )
                new_comment.pronostic = pronostic
                new_comment.author = request.user
                new_comment.save()
                messages.success( request, "Votre commentaire a été ajouté avec succès !" )
                return redirect( 'detail_pronostic', pk=pronostic.pk )
            else:
                for field, errors in comment_form.errors.items():
                    for error in errors:
                        messages.error( request, f"Erreur dans le champ '{field}': {error}" )
        else:
            messages.error( request, "Vous devez être connecté pour ajouter un commentaire." )
            comment_form = CommentForm()
    else:
        comment_form = CommentForm()

    context = get_base_context( request )
    context.update( {
        'pronostic': pronostic,
        'comments': comments,
        'comment_form': comment_form,
    } )
    return render( request, 'profoot/detail_pronostic.html', context )


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm( request.POST )
        if form.is_valid():
            user = form.save()
            login( request, user )
            messages.success( request,
                              f"Compte créé avec succès pour {user.username} ! Vous êtes maintenant connecté." )
            return redirect( 'liste_pronostics' )
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    field_name = form.fields[field].label if form.fields[field].label else field
                    messages.error( request, f"Erreur dans le champ '{field_name}': {error}" )
    else:
        form = CustomUserCreationForm()

    context = get_base_context( request )
    context.update( {'form': form} )
    return render( request, 'registration/register.html', context )


@login_required
def profile(request):
    user_pronostics = Pronostic.objects.filter( utilisateur=request.user ).order_by( '-date_match' )

    total_pronostics = user_pronostics.count()
    pronostics_gagnants = user_pronostics.filter( resultat='GAGNANT' )
    pronostics_perdants = user_pronostics.filter( resultat='PERDANT' )
    pronostics_en_cours = user_pronostics.filter( resultat='EN_COURS' )
    pronostics_annules = user_pronostics.filter( resultat='ANNULE' )

    total_gagnants = pronostics_gagnants.count()
    total_perdants = pronostics_perdants.count()
    total_en_cours = pronostics_en_cours.count()
    total_annules = pronostics_annules.count()

    pronostics_completes = user_pronostics.exclude( resultat__in=['EN_COURS', 'ANNULE'] )
    total_pronostics_completes = pronostics_completes.count()

    taux_reussite = 0
    if total_pronostics_completes > 0:
        taux_reussite = (total_gagnants / total_pronostics_completes) * 100

    profit_total = sum( p.gain_ou_perte for p in pronostics_completes )

    followers_count = request.user.follower_relations.count()
    following_count = request.user.following_relations.count()

    context = get_base_context( request )
    context.update( {
        'user': request.user,
        'user_pronostics': user_pronostics,
        'total_pronostics': total_pronostics,
        'total_gagnants': total_gagnants,
        'total_perdants': total_perdants,
        'total_en_cours': total_en_cours,
        'total_annules': total_annules,
        'taux_reussite': round( taux_reussite, 2 ),
        'profit_total': round( profit_total, 2 ),
        'followers_count': followers_count,
        'following_count': following_count,
    } )
    return render( request, 'registration/profile.html', context )


@login_required
@permission_required( 'profoot.add_pronostic', raise_exception=True )
def add_pronostic(request):
    initial_data = {}
    api_event_id_from_get = request.GET.get( 'api_event_id' )

    if api_event_id_from_get:
        event_details = get_event_details_from_sportmonks( api_event_id_from_get )
        if event_details:
            messages.success( request,
                              f"Détails du match pour '{event_details.get( 'event_name' )}' chargés avec succès depuis Sportmonks !" )

            # Note: date_match de event_details est un objet datetime.date
            # et heure_match est un objet datetime.time.
            # Nous combinons date et heure ici avant de passer au modèle.
            combined_datetime = None
            if event_details.get( 'date_match' ) and event_details.get( 'heure_match' ):
                # event_details['date_match'] est déjà un objet date (depuis event_datetime_obj.date())
                # event_details['heure_match'] est déjà un objet time (depuis event_datetime_obj.time())
                # combined_datetime doit être un datetime aware pour le modèle Match
                naive_combined = datetime.combine( event_details['date_match'], event_details['heure_match'] )
                combined_datetime = timezone.make_aware( naive_combined, timezone.get_current_timezone() )
            elif event_details.get( 'date_match' ):  # Si seule la date est dispo (ex: API ne donne pas l'heure)
                naive_combined = datetime.combine( event_details['date_match'], time( 0, 0 ) )  # Utilise minuit
                combined_datetime = timezone.make_aware( naive_combined, timezone.get_current_timezone() )

            match_obj, created_match = Match.objects.update_or_create(
                api_event_id=event_details['api_event_id'],
                defaults={
                    'discipline': event_details.get( 'discipline' ),
                    'equipe_domicile': event_details.get( 'equipe_domicile' ),
                    'equipe_exterieur': event_details.get( 'equipe_exterieur' ),
                    'date_match': combined_datetime,  # Utilise le datetime combiné
                    'ligue': event_details.get( 'ligue' ),
                    'stade': event_details.get( 'stade' ),
                    'score_final_domicile': event_details.get( 'score_final_domicile' ),
                    'score_final_exterieur': event_details.get( 'score_final_exterieur' ),
                    'status_api': event_details.get( 'status_event' ),
                }
            )

            initial_data['match'] = match_obj.pk

            initial_data['discipline'] = event_details.get( 'discipline' )
            initial_data['equipe_domicile'] = event_details.get( 'equipe_domicile' )
            initial_data['equipe_exterieur'] = event_details.get( 'equipe_exterieur' )
            initial_data['ligue'] = event_details.get( 'ligue' )
            initial_data['date_match'] = event_details.get( 'date_match' )
            initial_data['heure_match'] = event_details.get( 'heure_match' )
        else:
            messages.warning( request,
                              f"Aucun détail de match trouvé pour l'ID '{api_event_id_from_get}' fourni par Sportmonks ou erreur API. Veuillez vérifier l'ID et votre clé API." )
            initial_data = {}

    if request.method == 'POST':
        form = PronosticForm( request.POST )
        if form.is_valid():
            pronostic = form.save( commit=False )
            pronostic.utilisateur = request.user

            selected_match = form.cleaned_data.get( 'match' )
            if selected_match:
                pronostic.discipline = selected_match.discipline
                pronostic.equipe_domicile = selected_match.equipe_domicile
                pronostic.equipe_exterieur = selected_match.equipe_exterieur
                pronostic.date_match = selected_match.date_match
                pronostic.heure_match = selected_match.date_match.time()
                pronostic.ligue = selected_match.ligue

            pronostic.save()

            followers = request.user.follower_relations.all()
            for follow_obj in followers:
                Notification.objects.create(
                    recipient=follow_obj.follower,
                    sender=request.user,
                    notification_type='NEW_PRONOSTIC',
                    message=f"{request.user.username} a posté un nouveau pronostic ({pronostic.get_discipline_display()}): {pronostic.equipe_domicile} vs {pronostic.equipe_exterieur}.",
                    related_object=pronostic
                )
            messages.success( request, "Le pronostic a été ajouté avec succès !" )
            return redirect( 'liste_pronostics' )
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    field_name = form.fields[field].label if form.fields[field].label else field
                    messages.error( request, f"Erreur dans le champ '{field_name}': {error}" )
    else:
        form = PronosticForm( initial=initial_data )

    context = get_base_context( request )
    context.update( {
        'form': form,
        'page_title': "Ajouter un nouveau pronostic"
    } )
    return render( request, 'profoot/add_edit_pronostic.html', context )


@login_required
@permission_required( 'profoot.change_pronostic', raise_exception=True )
def edit_pronostic(request, pk):
    pronostic = get_object_or_404( Pronostic, pk=pk )

    if pronostic.utilisateur != request.user:
        messages.error( request, "Vous n'êtes pas autorisé à modifier ce pronostic." )
        return redirect( 'liste_pronostics' )

    initial_data = {}
    api_event_id_from_get = request.GET.get( 'api_event_id' )

    if api_event_id_from_get:
        event_details = get_event_details_from_sportmonks( api_event_id_from_get )
        if event_details:
            messages.success( request,
                              f"Détails du match pour '{event_details.get( 'event_name' )}' chargés avec succès depuis Sportmonks !" )

            combined_datetime = None
            if event_details.get( 'date_match' ) and event_details.get( 'heure_match' ):
                naive_combined = datetime.combine( event_details['date_match'], event_details['heure_match'] )
                combined_datetime = timezone.make_aware( naive_combined, timezone.get_current_timezone() )
            elif event_details.get( 'date_match' ):
                naive_combined = datetime.combine( event_details['date_match'], time( 0, 0 ) )
                combined_datetime = timezone.make_aware( naive_combined, timezone.get_current_timezone() )

            match_obj, created_match = Match.objects.update_or_create(
                api_event_id=event_details['api_event_id'],
                defaults={
                    'discipline': event_details.get( 'discipline' ),
                    'equipe_domicile': event_details.get( 'equipe_domicile' ),
                    'equipe_exterieur': event_details.get( 'equipe_exterieur' ),
                    'date_match': combined_datetime,
                    'ligue': event_details.get( 'ligue' ),
                    'stade': event_details.get( 'stade' ),
                    'score_final_domicile': event_details.get( 'score_final_domicile' ),
                    'score_final_exterieur': event_details.get( 'score_final_exterieur' ),
                    'status_api': event_details.get( 'status_event' ),
                }
            )

            initial_data['match'] = match_obj.pk

            initial_data['discipline'] = event_details.get( 'discipline' )
            initial_data['equipe_domicile'] = event_details.get( 'equipe_domicile' )
            initial_data['equipe_exterieur'] = event_details.get( 'equipe_exterieur' )
            initial_data['ligue'] = event_details.get( 'ligue' )
            initial_data['date_match'] = event_details.get( 'date_match' )
            initial_data['heure_match'] = event_details.get( 'heure_match' )
        else:
            messages.warning( request,
                              f"Aucun détail de match trouvé pour l'ID '{api_event_id_from_get}' Sportmonks fourni ou erreur API. Veuillez vérifier l'ID." )

    if request.method == 'POST':
        form = PronosticForm( request.POST, instance=pronostic )
        if form.is_valid():
            pronostic = form.save( commit=False )

            selected_match = form.cleaned_data.get( 'match' )
            if selected_match:
                pronostic.discipline = selected_match.discipline
                pronostic.equipe_domicile = selected_match.equipe_domicile
                pronostic.equipe_exterieur = selected_match.equipe_exterieur
                pronostic.date_match = selected_match.date_match
                pronostic.heure_match = selected_match.date_match.time()
                pronostic.ligue = selected_match.ligue

            form.save()
            messages.success( request, "Le pronostic a été mis à jour avec succès !" )
            return redirect( 'detail_pronostic', pk=pronostic.pk )
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    field_name = form.fields[field].label if form.fields[field].label else field
                    messages.error( request, f"Erreur dans le champ '{field_name}': {error}" )
    else:
        if pronostic.match:
            initial_data['match'] = pronostic.match.pk
            initial_data['discipline'] = pronostic.match.discipline
            initial_data['equipe_domicile'] = pronostic.match.equipe_domicile
            initial_data['equipe_exterieur'] = pronostic.match.equipe_exterieur
            initial_data['ligue'] = pronostic.match.ligue
            initial_data['date_match'] = pronostic.match.date_match.date()
            initial_data['heure_match'] = pronostic.match.date_match.time()

        form = PronosticForm( instance=pronostic, initial=initial_data )

    context = get_base_context( request )
    context.update( {
        'form': form,
        'page_title': "Modifier le pronostic"
    } )
    return render( request, 'profoot/add_edit_pronostic.html', context )


@login_required
@permission_required( 'profoot.delete_pronostic', raise_exception=True )
def delete_pronostic(request, pk):
    pronostic = get_object_or_404( Pronostic, pk=pk )

    if pronostic.utilisateur != request.user:
        messages.error( request, "Vous n'êtes pas autorisé à supprimer ce pronostic." )
        return redirect( 'liste_pronostics' )

    if request.method == 'POST':
        pronostic.delete()
        messages.success( request, "Le pronostic a été supprimé avec succès." )
        return redirect( 'liste_pronostics' )

    context = get_base_context( request )
    context.update( {'pronostic': pronostic} )
    return render( request, 'profoot/confirm_delete_pronostic.html', context )


def public_profile(request, username):
    other_user = get_object_or_404( User, username=username )
    other_user_pronostics = Pronostic.objects.filter( utilisateur=other_user ).order_by( '-date_match' )

    total_pronostics = other_user_pronostics.count()
    pronostics_gagnants = other_user_pronostics.filter( resultat='GAGNANT' )
    pronostics_perdants = other_user_pronostics.filter( resultat='PERDANT' )
    pronostics_en_cours = other_user_pronostics.filter( resultat='EN_COURS' )
    pronostics_annules = other_user_pronostics.filter( resultat='ANNULE' )

    total_gagnants = pronostics_gagnants.count()
    total_perdants = pronostics_perdants.count()
    total_en_cours = pronostics_en_cours.count()
    total_annules = pronostics_annules.count()

    pronostics_completes = other_user_pronostics.exclude( resultat__in=['EN_COURS', 'ANNULE'] )
    total_pronostics_completes = pronostics_completes.count()

    taux_reussite = 0
    if total_pronostics_completes > 0:
        taux_reussite = (total_gagnants / total_pronostics_completes) * 100

    profit_total = sum( p.gain_ou_perte for p in pronostics_completes )

    followers_count = other_user.follower_relations.count()
    following_count = other_user.following_relations.count()

    is_following = False
    if request.user.is_authenticated:
        is_following = Follow.objects.filter( follower=request.user, following=other_user ).exists()

    context = get_base_context( request )
    context.update( {
        'user_being_viewed': other_user,
        'user_pronostics': other_user_pronostics,
        'total_pronostics': total_pronostics,
        'total_gagnants': total_gagnants,
        'total_perdants': total_perdants,
        'total_en_cours': total_en_cours,
        'total_annules': total_annules,
        'taux_reussite': round( taux_reussite, 2 ),
        'profit_total': round( profit_total, 2 ),
        'followers_count': followers_count,
        'following_count': following_count,
        'is_following': is_following,
    } )
    return render( request, 'registration/public_profile.html', context )


@login_required
def follow_user(request, username):
    user_to_follow = get_object_or_404( User, username=username )
    current_user = request.user

    if current_user == user_to_follow:
        messages.error( request, "Vous ne pouvez pas vous suivre vous-même." )
        return redirect( 'public_profile', username=username )

    try:
        Follow.objects.create( follower=current_user, following=user_to_follow )
        Notification.objects.create(
            recipient=user_to_follow,
            sender=current_user,
            notification_type='FOLLOW',
            message=f"{current_user.username} a commencé à vous suivre !",
            related_object=current_user
        )
        messages.success( request, f"Vous suivez maintenant {user_to_follow.username} !" )
    except Exception as e:
        messages.info( request, f"Vous suivez déjà {user_to_follow.username}." )

    return redirect( 'public_profile', username=username )


@login_required
def unfollow_user(request, username):
    user_to_unfollow = get_object_or_404( User, username=username )
    current_user = request.user

    deleted_count, _ = Follow.objects.filter( follower=current_user, following=user_to_unfollow ).delete()

    if deleted_count > 0:
        messages.success( request, f"Vous ne suivez plus {user_to_unfollow.username}." )
    else:
        messages.info( request, f"Vous ne suiviez déjà pas {user_to_unfollow.username}." )

    return redirect( 'public_profile', username=username )


@login_required
def followed_pronostics_feed(request):
    followed_users_ids = request.user.following_relations.values_list( 'following__id', flat=True )

    followed_pronostics = Pronostic.objects.filter(
        utilisateur__id__in=followed_users_ids
    ).exclude(
        utilisateur__isnull=True
    ).order_by( '-date_match' )

    paginator = Paginator( followed_pronostics, 5 )
    page_number = request.GET.get( 'page' )
    page_obj = paginator.get_page( page_number )

    context = get_base_context( request )
    context.update( {
        'page_obj': page_obj,
        'has_followed_users': bool( followed_users_ids )
    } )
    return render( request, 'profoot/followed_pronostics_feed.html', context )


@login_required
def notification_list(request):
    notifications = Notification.objects.filter( recipient=request.user ).order_by( '-created_at' )

    unread_notifications = notifications.filter( is_read=False )
    unread_notifications.update( is_read=True )

    paginator = Paginator( notifications, 10 )
    page_number = request.GET.get( 'page' )
    page_obj = paginator.get_page( page_number )

    context = get_base_context( request )
    context.update( {
        'page_obj': page_obj,
    } )
    return render( request, 'profoot/notification_list.html', context )


@login_required
def toggle_theme(request):
    if request.user.is_authenticated:
        profile, created = UserProfile.objects.get_or_create( user=request.user )
        if profile.theme_preference == 'light':
            profile.theme_preference = 'dark'
            messages.info( request, "Thème sombre activé." )
        else:
            profile.theme_preference = 'light'
            messages.info( request, "Thème clair activé." )
        profile.save()
    return redirect( request.META.get( 'HTTP_REFERER', 'liste_pronostics' ) )


def promo_codes_view(request):
    offers = BookmakerOffer.objects.filter( is_active=True ).order_by( 'order' )
    context = {
        'offers': offers
    }
    return render( request, 'profoot/promo_codes.html', context )

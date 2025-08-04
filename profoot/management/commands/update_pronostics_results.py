# profoot/management/commands/update_pronostics_results.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from profoot.models import Pronostic, Match # <-- CORRECTION ICI : Importation absolue
from profoot.api_integrations import update_pronostic_from_api_data, fetch_and_store_upcoming_matches

class Command(BaseCommand):
    help = 'Gère la mise à jour des scores et statuts des pronostics terminés, et/ou la récupération des matchs à venir depuis Sportmonks.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fetch-matches',
            action='store_true',
            help='Récupère et stocke les matchs à venir de l\'API Sportmonks.',
        )
        parser.add_argument(
            '--days-in-advance',
            type=int,
            default=7,
            help='Nombre de jours dans le futur pour la récupération des matchs (utilisé avec --fetch-matches).',
        )
        parser.add_argument(
            '--update-pronostics',
            action='store_true',
            help='Met à jour les scores et statuts des pronostics existants.',
        )

    def handle(self, *args, **options):
        fetch_matches_enabled = options['fetch_matches']
        update_pronostics_enabled = options['update_pronostics']

        if not fetch_matches_enabled and not update_pronostics_enabled:
            fetch_matches_enabled = True
            update_pronostics_enabled = True

        if fetch_matches_enabled:
            self.stdout.write(self.style.SUCCESS('Démarrage de la récupération et du stockage des matchs à venir depuis Sportmonks...'))
            days_in_advance = options['days_in_advance']
            added, updated = fetch_and_store_upcoming_matches(days_in_advance=days_in_advance)
            self.stdout.write(self.style.SUCCESS(f'Récupération des matchs terminée. Ajoutés : {added}, Mis à jour : {updated}'))

        if update_pronostics_enabled:
            self.stdout.write(self.style.SUCCESS('Démarrage de la mise à jour des pronostics existants...'))

            # Récupérer les pronostics qui sont "EN_COURS" et dont le match est passé ou est en cours
            # Nous utilisons une fenêtre de 2 heures après l'heure actuelle pour s'assurer de ne pas manquer les matchs
            # qui viennent de commencer ou qui sont en cours.
            pronostics_to_update = Pronostic.objects.filter(
                # Utiliser la date_match du modèle Match lié pour le filtrage
                match__date_match__lte=timezone.now() + timedelta(hours=2),
                resultat__in=['EN_COURS']
            ).order_by('match__date_match') # Trier par la date du match lié

            if not pronostics_to_update.exists():
                self.stdout.write(self.style.WARNING('Aucun pronostic à mettre à jour pour le moment.'))

            updated_count = 0
            skipped_count = 0
            error_count = 0

            for pronostic in pronostics_to_update:
                try:
                    # Vérifiez si le pronostic a un match lié
                    if not pronostic.match:
                        self.stdout.write(self.style.WARNING(f"Pronostic ID {pronostic.pk} - Pas de match lié. Ignoré."))
                        skipped_count += 1
                        continue

                    self.stdout.write(f"Traitement du pronostic ID {pronostic.pk} (Match: {pronostic.match.equipe_domicile} vs {pronostic.match.equipe_exterieur}, API ID: {pronostic.match.api_event_id})...")
                    if update_pronostic_from_api_data(pronostic):
                        updated_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Erreur lors de la mise à jour du pronostic ID {pronostic.pk}: {e}"))
                    error_count += 1

            self.stdout.write(self.style.SUCCESS(f'Processus de mise à jour des pronostics terminé.'))
            self.stdout.write(self.style.SUCCESS(f'Pronostics mis à jour : {updated_count}'))
            self.stdout.write(self.style.WARNING(f'Pronostics ignorés (pas de résultat final ou match non lié) : {skipped_count}'))
            self.stdout.write(self.style.ERROR(f'Erreurs rencontrées : {error_count}'))

        self.stdout.write(self.style.SUCCESS('Opération de gestion des pronostics et matchs terminée.'))


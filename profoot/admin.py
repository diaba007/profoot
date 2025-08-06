# profoot/admin.py

from django.contrib import admin
from .models import Pronostic, Comment, BookmakerOffer, Follow, Notification, UserProfile, Match # Assurez-vous d'importer Match
from .forms import PronosticAdminForm # Importez votre formulaire personnalisé

# Enregistrement des modèles existants avec la syntaxe @admin.register
@admin.register(Pronostic)
class PronosticAdmin(admin.ModelAdmin):
    form = PronosticAdminForm # Utilise le formulaire personnalisé

    list_display = ('match', 'discipline', 'type_pari', 'resultat', 'utilisateur')
    list_filter = ('discipline', 'resultat', 'match__date_match')
    search_fields = ('match__equipe_domicile', 'match__equipe_exterieur', 'prediction_details')
    date_hierarchy = 'match__date_match'

    fieldsets = (
        ('Match', {
            'fields': ('match',)
        }),
        ('Création de Match Manuel', {
            'fields': ('equipe_domicile_manuelle', 'equipe_exterieur_manuelle', 'date_match_manuelle', 'ligue_manuelle'),
            'description': 'Utilisez cette section si le match n\'est pas dans la liste ci-dessus. Laissez vide si vous sélectionnez un match existant.'
        }),
        ('Détails du Pronostic', {
            'fields': ('discipline', 'type_pari', 'prediction_details', 'cote', 'mise', 'bookmaker_recommande', 'lien_pari')
        }),
        ('Résultat', {
            'fields': ('resultat',)
        }),
    )

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('equipe_domicile', 'equipe_exterieur', 'date_match', 'ligue', 'api_event_id')
    search_fields = ('equipe_domicile', 'equipe_exterieur', 'ligue')
    list_filter = ('ligue', 'discipline')
    # Vous pouvez également rendre 'api_event_id' en lecture seule pour les matchs non-API
    # readonly_fields = ('api_event_id',) 

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('pronostic', 'author', 'created_at', 'content')
    list_filter = ('created_at', 'author')
    search_fields = ('content',)
    raw_id_fields = ('pronostic', 'author')

# Ajoutez les autres @admin.register si vous les aviez
@admin.register(BookmakerOffer)
class BookmakerOfferAdmin(admin.ModelAdmin):
    list_display = ('name', 'bonus_description', 'promo_code', 'registration_link', 'order', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'bonus_description')
    ordering = ('order',)

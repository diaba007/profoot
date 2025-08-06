# profoot/admin.py

from django.contrib import admin
# Assurez-vous que tous vos modèles utilisés sont importés ici
from .models import Pronostic, Comment, BookmakerOffer, Follow, Notification, UserProfile

# Enregistrement des modèles existants avec la syntaxe @admin.register
# Remplacez votre "admin.site.register(Pronostic)" par ce bloc pour Pronostic
@admin.register(Pronostic)
class PronosticAdmin(admin.ModelAdmin):
    list_display = ('equipe_domicile', 'equipe_exterieur', 'date_match', 'discipline', 'resultat', 'utilisateur')
    list_filter = ('discipline', 'resultat', 'date_match')
    search_fields = ('equipe_domicile', 'equipe_exterieur', 'prediction_details')
    date_hierarchy = 'date_match'

# Si vous avez d'autres modèles comme Comment, Follow, Notification, UserProfile
# assurez-vous qu'ils sont enregistrés de manière similaire ou selon votre configuration existante.
# Exemple pour Comment :
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('pronostic', 'author', 'created_at', 'content')
    list_filter = ('created_at', 'author')
    search_fields = ('content',)
    raw_id_fields = ('pronostic', 'author')

# Ajoutez les autres @admin.register pour Follow, Notification, UserProfile si vous les aviez
# et que vous voulez qu'ils aient des options d'affichage spécifiques dans l'admin.
# Sinon, un simple admin.site.register(MyModel) fonctionnerait aussi pour eux.

# ENREGISTREMENT DU NOUVEAU MODÈLE BOOKMAKEROFFER
@admin.register(BookmakerOffer)
class BookmakerOfferAdmin(admin.ModelAdmin):
    list_display = ('name', 'bonus_description', 'promo_code', 'registration_link', 'order', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'bonus_description')
    ordering = ('order',)

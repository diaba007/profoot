from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


# --- NOUVEAU MODÈLE : Match ---
# Ce modèle stockera les informations des matchs récupérées depuis Sportmonks.
# Il est centralisé et permettra de lier plusieurs pronostics à un même match.
class Match( models.Model ):
    # L'ID de l'événement Sportmonks. Il est unique pour chaque match.
    # Sportmonks utilise des IDs numériques, BigIntegerField est approprié.
    api_event_id = models.BigIntegerField( unique=True, db_index=True, verbose_name="ID d'événement Sportmonks" )

    discipline = models.CharField( max_length=50, default='FOOTBALL',
                                   verbose_name="Discipline" )  # Peut être récupéré de l'API
    equipe_domicile = models.CharField( max_length=100, verbose_name="Équipe Domicile" )
    equipe_exterieur = models.CharField( max_length=100, verbose_name="Équipe Extérieure" )

    # Date et heure du match. DateTimeField est idéal pour le format ISO de Sportmonks.
    date_match = models.DateTimeField( verbose_name="Date et Heure du Match" )

    ligue = models.CharField( max_length=100, blank=True, null=True, verbose_name="Ligue" )
    stade = models.CharField( max_length=100, blank=True, null=True, verbose_name="Stade" )  # Nouveau champ potentiel

    # Scores finaux (peuvent être mis à jour par la commande de mise à jour)
    score_final_domicile = models.IntegerField( null=True, blank=True, verbose_name="Score Final Domicile" )
    score_final_exterieur = models.IntegerField( null=True, blank=True, verbose_name="Score Final Extérieur" )

    # Statut du match (ex: 'Not Started', 'Live', 'Finished', 'Cancelled', etc.)
    # Peut être utile pour l'affichage ou des logiques complexes.
    # Vous pouvez stocker l'ID numérique ou la chaîne de statut de Sportmonks.
    status_api = models.CharField( max_length=50, blank=True, null=True, verbose_name="Statut API du Match" )

    date_creation = models.DateTimeField( auto_now_add=True )
    date_mise_a_jour = models.DateTimeField( auto_now=True )

    class Meta:
        verbose_name = "Match Sportif"
        verbose_name_plural = "Matchs Sportifs"
        ordering = ['date_match']  # Trier les matchs par date

    def __str__(self):
        return f"{self.equipe_domicile} vs {self.equipe_exterieur} ({self.ligue}) le {self.date_match.strftime( '%Y-%m-%d %H:%M' )}"


# Modèle pour représenter un pronostic sportif
class Pronostic( models.Model ):
    # Options prédéfinies pour les champs
    DISCIPLINE_CHOICES = [
        ('FOOTBALL', 'Football'),
        ('TENNIS', 'Tennis'),
        ('BASKETBALL', 'Basketball'),
    ]
    STATUT_CHOICES = [
        ('EN_COURS', 'À venir'),
        ('GAGNANT', 'Gagnant'),
        ('PERDANT', 'Perdant'),
        ('ANNULE', 'Annulé'),
    ]
    TYPE_PARI_CHOICES = [
        ('1N2', '1N2 (Résultat du match)'),
        ('OVER_UNDER', 'Over/Under (Total de points/buts)'),
        ('HANDICAP', 'Handicap'),
        ('BUTEUR', 'Buteur/Marqueur'),
        ('DOUBLE_CHANCE', 'Double Chance'),
        ('MI_TEMPS_FIN_MATCH', 'Mi-temps/Fin de match'),
        ('SCORE_EXACT', 'Score Exact'),
        ('AUTRE', 'Autre'),
    ]

    # Informations générales du pronostic
    discipline = models.CharField( max_length=50, choices=DISCIPLINE_CHOICES, default='FOOTBALL',
                                   verbose_name="Discipline" )
    type_pari = models.CharField( max_length=50, choices=TYPE_PARI_CHOICES, default='1N2', verbose_name="Type de pari" )

    # --- CHANGEMENT MAJEUR : Liaison avec le modèle Match ---
    # Au lieu d'un simple CharField pour api_event_id, nous allons le lier à notre nouveau modèle Match.
    # Cela permet de centraliser les informations du match et d'éviter la redondance.
    match = models.ForeignKey( Match, on_delete=models.CASCADE, related_name='pronostics',
                               verbose_name="Match Associé" )

    # Les champs suivants (equipe_domicile, equipe_exterieur, date_match, heure_match, ligue, score_final_domicile, score_final_exterieur)
    # sont maintenant redondants s'ils sont déjà dans le modèle Match.
    # Vous pouvez choisir de les supprimer de Pronostic et d'accéder aux informations via pronostic.match.
    # Pour une transition plus douce, je les laisse pour l'instant, mais c'est une opportunité d'optimisation.
    # Si vous les laissez, ils seront pré-remplis mais la source de vérité sera le modèle Match.
    equipe_domicile = models.CharField( max_length=100, blank=True, null=True,
                                        help_text="Nom de l'équipe domicile (du match associé)" )
    equipe_exterieur = models.CharField( max_length=100, blank=True, null=True,
                                         help_text="Nom de l'équipe extérieure (du match associé)" )
    date_match = models.DateTimeField( blank=True, null=True, help_text="Date et heure du match (du match associé)" )
    heure_match = models.TimeField( null=True, blank=True,
                                    help_text="Heure du match (du match associé)" )  # Ce champ peut être dérivé de date_match
    ligue = models.CharField( max_length=100, blank=True, null=True, help_text="Ligue du match (du match associé)" )

    # L'ancien api_event_id devient la clé étrangère. On peut le garder pour des raisons de compatibilité si besoin,
    # mais il est préférable de le supprimer et d'utiliser `match.api_event_id`.
    # Si vous le gardez, changez son verbose_name pour éviter la confusion.
    # api_event_id = models.BigIntegerField(null=True, blank=True, verbose_name="Ancien ID d'événement API (obsolète)")

    # Détails de la prédiction
    prediction_score = models.CharField( max_length=50, blank=True, null=True,
                                         verbose_name="Prédiction de score (optionnel)" )
    prediction_details = models.TextField( verbose_name="Analyse et détails de la prédiction" )
    cote = models.DecimalField( max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Cote" )
    mise = models.DecimalField( max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Mise (€)" )

    # Résultat et score final
    resultat = models.CharField( max_length=50, choices=STATUT_CHOICES, default='EN_COURS',
                                 verbose_name="Statut du pronostic" )
    # Les scores finaux devraient idéalement venir du modèle Match.
    # Pour l'instant, je les laisse ici pour une transition plus douce, mais c'est une redondance.
    score_final_domicile = models.IntegerField( null=True, blank=True, verbose_name="Score final domicile" )
    score_final_exterieur = models.IntegerField( null=True, blank=True, verbose_name="Score final extérieur" )

    date_creation = models.DateTimeField( auto_now_add=True )

    # Lien vers l'utilisateur ayant créé le pronostic (clé étrangère vers le modèle User de Django)
    utilisateur = models.ForeignKey( User, on_delete=models.CASCADE, related_name='pronostics', null=True, blank=True )

    # NOUVEAU CHAMP : Bookmaker recommandé (ForeignKey vers BookmakerOffer)
    bookmaker_recommande = models.ForeignKey(
        'BookmakerOffer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pronostics_lies',
        verbose_name="Bookmaker Recommandé",
        help_text="Bookmaker où ce pronostic pourrait être placé."
    )
    # NOUVEAU CHAMP : Lien direct pour parier sur le bookmaker pour ce match (optionnel)
    lien_pari = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Lien direct vers le pari",
        help_text="URL directe vers le match ou le pari sur le site du bookmaker."
    )

    @property
    def gain_ou_perte(self):
        """Calcule le gain ou la perte basé sur la mise, la cote et le résultat."""
        if self.mise is None:
            return 0
        if self.resultat == 'GAGNANT':
            return self.mise * (self.cote - 1) if self.cote is not None else 0
        elif self.resultat == 'PERDANT':
            return -self.mise
        else:
            return 0

    def __str__(self):
        # Utiliser les informations du match lié pour une meilleure description
        if self.match:
            return f"[{self.get_discipline_display()}] {self.match.equipe_domicile} vs {self.match.equipe_exterieur} le {self.match.date_match.strftime( '%Y-%m-%d %H:%M' )}"
        return f"[{self.get_discipline_display()}] Pronostic sans match lié ({self.pk})"

    class Meta:
        ordering = ['-date_match']  # Peut être ajusté pour trier par match.date_match
        verbose_name = "Pronostic Sportif"
        verbose_name_plural = "Pronostics Sportifs"


# Modèle pour la gestion des relations de suivi (Follow/Unfollow)
class Follow( models.Model ):
    follower = models.ForeignKey( User, on_delete=models.CASCADE, related_name='following_relations' )
    following = models.ForeignKey( User, on_delete=models.CASCADE, related_name='follower_relations' )
    date_followed = models.DateTimeField( auto_now_add=True )

    class Meta:
        unique_together = ('follower', 'following')
        verbose_name = "Suivi"
        verbose_name_plural = "Suivis"

    def __str__(self):
        return f"{self.follower.username} suit {self.following.username}"


# Modèle pour les notifications utilisateur
class Notification( models.Model ):
    NOTIFICATION_TYPES = (
        ('FOLLOW', 'Nouvel abonné'),
        ('NEW_PRONOSTIC', 'Nouveau pronostic'),
    )

    recipient = models.ForeignKey( User, on_delete=models.CASCADE, related_name='notifications',
                                   verbose_name="Destinataire" )
    sender = models.ForeignKey( User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='sent_notifications', verbose_name="Expéditeur" )
    notification_type = models.CharField( max_length=20, choices=NOTIFICATION_TYPES,
                                          verbose_name="Type de notification" )
    message = models.TextField( verbose_name="Message" )
    created_at = models.DateTimeField( auto_now_add=True, verbose_name="Date de création" )
    is_read = models.BooleanField( default=False, verbose_name="Lu" )
    related_object_id = models.PositiveIntegerField( null=True, blank=True )
    related_object_content_type = models.ForeignKey( ContentType, on_delete=models.CASCADE, null=True, blank=True )
    related_object = GenericForeignKey( 'related_object_content_type', 'related_object_id' )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"Notification pour {self.recipient.username}: {self.message[:50]}..."


# Modèle pour les commentaires sur les pronostics
class Comment( models.Model ):
    pronostic = models.ForeignKey( Pronostic, on_delete=models.CASCADE, related_name='comments',
                                   verbose_name="Pronostic" )
    author = models.ForeignKey( User, on_delete=models.CASCADE, related_name='user_comments', verbose_name="Auteur" )
    content = models.TextField( verbose_name="Contenu du commentaire" )
    created_at = models.DateTimeField( auto_now_add=True, verbose_name="Date de création" )

    class Meta:
        ordering = ['created_at']
        verbose_name = "Commentaire"
        verbose_name_plural = "Commentaires"

    def __str__(self):
        if self.pronostic:
            return f"Commentaire de {self.author.username} sur {self.pronostic.get_discipline_display()} - {self.pronostic.equipe_domicile} vs {self.pronostic.equipe_exterieur}"
        return f"Commentaire de {self.author.username}"


# Modèle pour stocker les préférences utilisateur (par exemple, le thème)
class UserProfile( models.Model ):
    user = models.OneToOneField( User, on_delete=models.CASCADE, related_name='profile', verbose_name="Utilisateur" )
    theme_preference = models.CharField(
        max_length=10,
        choices=[
            ('light', 'Clair'),
            ('dark', 'Sombre'),
        ],
        default='light',
        verbose_name="Préférence de thème"
    )

    class Meta:
        verbose_name = "Profil Utilisateur"
        verbose_name_plural = "Profils Utilisateurs"

    def __str__(self):
        return f"Profil de {self.user.username}"


# Modèle pour les offres des bookmakers (déjà existant et utilisé)
class BookmakerOffer( models.Model ):
    name = models.CharField( max_length=100, verbose_name="Nom du Bookmaker" )
    bonus_description = models.CharField( max_length=255, verbose_name="Description du Bonus" )
    promo_code = models.CharField( max_length=50, blank=True, null=True, verbose_name="Code Promo" )
    registration_link = models.URLField( verbose_name="Lien d'inscription" )
    logo = models.ImageField( upload_to='bookmaker_logos/', blank=True, null=True, verbose_name="Logo" )
    order = models.IntegerField( default=0, verbose_name="Ordre d'affichage" )
    is_active = models.BooleanField( default=True, verbose_name="Actif" )
    created_at = models.DateTimeField( auto_now_add=True )
    updated_at = models.DateTimeField( auto_now=True )

    class Meta:
        verbose_name = "Offre de Bookmaker"
        verbose_name_plural = "Offres de Bookmakers"
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

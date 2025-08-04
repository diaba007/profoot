from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from .models import Pronostic, Comment, BookmakerOffer, Match # <-- AJOUTEZ Match ici
from django.utils import timezone

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = UserCreationForm.Meta.fields + ('email',)

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = get_user_model()
        fields = UserChangeForm.Meta.fields

class PronosticForm(forms.ModelForm):
    # Le champ 'match' est une clé étrangère vers le modèle Match.
    # Django va automatiquement créer un Select widget pour cela.
    # Nous pourrions vouloir le rendre invisible ou en lecture seule
    # si le match est toujours sélectionné via l'ID API dans la vue.
    # Pour l'instant, nous le laissons comme un champ standard.
    class Meta:
        model = Pronostic
        fields = [
            'match', # <-- REMPLACE api_event_id par match (ForeignKey)
            'discipline',
            'type_pari',
            # Les champs suivants sont maintenant idéalement tirés de l'objet Match lié,
            # mais sont laissés ici pour une transition plus douce et si vous voulez permettre
            # une saisie manuelle ou un affichage dans le formulaire.
            # Ils devraient être en lecture seule si vous voulez qu'ils reflètent uniquement le Match.
            'equipe_domicile',
            'equipe_exterieur',
            'date_match',
            'heure_match',
            'ligue',
            'prediction_details',
            'prediction_score',
            'cote',
            'mise',
            'resultat',
            # 'score_final_domicile', # <-- SUPPRIMÉ : Ces scores sont sur le modèle Match
            # 'score_final_exterieur', # <-- SUPPRIMÉ : Ces scores sont sur le modèle Match
            'bookmaker_recommande',
            'lien_pari',
        ]
        widgets = {
            'match': forms.Select(attrs={'class': 'form-select'}), # Widget pour la sélection du match
            'discipline': forms.Select(attrs={'class': 'form-select'}),
            'type_pari': forms.Select(attrs={'class': 'form-select'}),
            'date_match': forms.DateInput(attrs={'type': 'date', 'class': 'form-control', 'readonly': 'readonly'}), # Lecture seule
            'heure_match': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control', 'readonly': 'readonly'}), # Lecture seule
            'ligue': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}), # Lecture seule
            'equipe_domicile': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}), # Lecture seule
            'equipe_exterieur': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}), # Lecture seule
            'prediction_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'prediction_score': forms.TextInput(attrs={'class': 'form-control'}),
            'cote': forms.NumberInput(attrs={'class': 'form-control'}),
            'mise': forms.NumberInput(attrs={'class': 'form-control'}),
            'resultat': forms.Select(attrs={'class': 'form-select'}),
            # 'score_final_domicile': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}), # SUPPRIMÉ
            # 'score_final_exterieur': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}), # SUPPRIMÉ
            'bookmaker_recommande': forms.Select(attrs={'class': 'form-select'}),
            'lien_pari': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Ex: https://www.bookmaker.com/pari-match'}),
        }
        labels = {
            'match': "Match Associé", # Nouveau label
            'discipline': "Discipline Sportive",
            'type_pari': "Type de pari",
            'date_match': "Date du match (auto-remplie)",
            'heure_match': "Heure du match (auto-remplie)",
            'ligue': "Ligue (auto-remplie)",
            'equipe_domicile': "Équipe à domicile (auto-remplie)",
            'equipe_exterieur': "Équipe à l'extérieur (auto-remplie)",
            'prediction_details': "Analyse et détails de la prédiction",
            'prediction_score': "Prédiction de score (optionnel)",
            'cote': "Cote",
            'mise': "Mise (€)",
            'resultat': "Statut du pronostic",
            # 'score_final_domicile': "Score final (domicile)", # SUPPRIMÉ
            # 'score_final_exterieur': "Score final (extérieur)", # SUPPRIMÉ
            'bookmaker_recommande': "Bookmaker Recommandé",
            'lien_pari': "Lien Direct Vers le Pari",
        }

    # Méthode __init__ pour filtrer les options du champ 'match'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limite les options du champ 'match' aux matchs qui n'ont pas encore commencé
        # ou qui sont en cours (si vous voulez permettre des pronostics "live").
        # Vous pouvez ajuster ce filtre selon votre logique métier.
        self.fields['match'].queryset = Match.objects.filter(date_match__gte=timezone.now()).order_by('date_match')
        # Ou pour inclure les matchs en cours:
        # self.fields['match'].queryset = Match.objects.filter(
        #     Q(date_match__gte=timezone.now()) | Q(status_api='Live') # Adaptez 'Live' au statut Sportmonks
        # ).order_by('date_match')


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ajoutez votre commentaire ici...'}),
        }
        labels = {
            'content': 'Votre commentaire',
        }

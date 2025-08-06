from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from .models import Pronostic, Comment, BookmakerOffer, Match
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
    # Champs pour la création manuelle d'un match
    equipe_domicile_manuelle = forms.CharField(max_length=100, required=False, label="Équipe Domicile (Manuelle)")
    equipe_exterieur_manuelle = forms.CharField(max_length=100, required=False, label="Équipe Extérieure (Manuelle)")
    date_match_manuelle = forms.DateTimeField(required=False, label="Date du Match (Manuelle)",
                                              widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}))
    ligue_manuelle = forms.CharField(max_length=100, required=False, label="Ligue (Manuelle)")

    class Meta:
        model = Pronostic
        fields = [
            'match',
            'discipline',
            'type_pari',
            'prediction_details',
            'cote',
            'mise',
            'bookmaker_recommande',
            'lien_pari',
        ]

        widgets = {
            'match': forms.Select(attrs={'class': 'form-select'}),
            'discipline': forms.Select(attrs={'class': 'form-select'}),
            'type_pari': forms.Select(attrs={'class': 'form-select'}),
            'prediction_details': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'cote': forms.NumberInput(attrs={'class': 'form-control'}),
            'mise': forms.NumberInput(attrs={'class': 'form-control'}),
            'bookmaker_recommande': forms.Select(attrs={'class': 'form-select'}),
            'lien_pari': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'Ex: https://www.bookmaker.com/pari-match'}),
        }
        labels = {
            'match': "Match Associé (sélectionnez dans la liste)",
            'discipline': "Discipline Sportive",
            'type_pari': "Type de pari",
            'prediction_details': "Analyse et détails de la prédiction",
            'cote': "Cote",
            'mise': "Mise (€)",
            'bookmaker_recommande': "Bookmaker Recommandé",
            'lien_pari': "Lien Direct Vers le Pari",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['match'].queryset = Match.objects.filter(date_match__gte=timezone.now()).order_by('date_match')
        # Rendre le champ match optionnel au niveau du formulaire
        self.fields['match'].required = False

    def clean(self):
        cleaned_data = super().clean()
        match = cleaned_data.get('match')
        equipe_domicile_manuelle = cleaned_data.get('equipe_domicile_manuelle')
        date_match_manuelle = cleaned_data.get('date_match_manuelle')

        if not match and not equipe_domicile_manuelle:
            # Si aucun match n'est sélectionné et qu'aucun champ manuel n'est rempli
            raise forms.ValidationError(
                "Vous devez soit sélectionner un match existant, soit en créer un manuellement."
            )
        
        if not match and equipe_domicile_manuelle and not date_match_manuelle:
            # S'il manque des informations pour le match manuel
            raise forms.ValidationError(
                "Veuillez remplir au moins le nom des équipes et la date pour créer un match."
            )

        # Si les champs manuels sont remplis, créer le match
        if not match and equipe_domicile_manuelle and date_match_manuelle:
            new_match, created = Match.objects.get_or_create(
                equipe_domicile=equipe_domicile_manuelle,
                equipe_exterieur=cleaned_data.get('equipe_exterieur_manuelle', ''),
                date_match=date_match_manuelle,
                ligue=cleaned_data.get('ligue_manuelle', ''),
                defaults={'api_event_id': None}
            )
            cleaned_data['match'] = new_match

        return cleaned_data

# profoot/signals.py

from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import UserProfile

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    # Si l'utilisateur existait déjà, on pourrait aussi gérer des mises à jour ici si nécessaire
    # instance.profile.save() # Utile si vous avez des champs qui se mettent à jour avec l'utilisateur
# C:\Users\pc.DESKTOP-83C180U\Desktop\ProjetDjango\profoot\urls.py
# C'EST VOTRE FICHIER D'URLS PRINCIPAL DU PROJET, ET NON CELUI DE L'APPLICATION.
# Il contient toutes les URLs car ROOT_URLCONF pointe directement vers lui.

from django.contrib import admin
# Incluez 'include' car il est utilisé pour django.contrib.auth.urls
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Importez directement les vues de l'application 'profoot'
# car il n'y aura plus de fichier urls.py distinct pour l'application si celui-ci est le principal.
from profoot import views

urlpatterns = [
    # C'est l'URL de l'admin. Le 'admin.site.urls' fournit le namespace 'admin'.
    path('admin/', admin.site.urls),

    # Les URLs de votre application 'profoot' sont maintenant directement définies ici.
    # Il ne doit PAS y avoir de 'path('', include('profoot.urls'))' ici car ce fichier EST 'profoot.urls'.
    path('', views.liste_pronostics, name='liste_pronostics'),
    path('pronostic/<int:pk>/', views.detail_pronostic, name='detail_pronostic'),

    # Ces URLs pour l'authentification sont incluses ici, ce qui est correct.
    path('accounts/', include('django.contrib.auth.urls')),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('add_pronostic/', views.add_pronostic, name='add_pronostic'),
    path('pronostic/<int:pk>/edit/', views.edit_pronostic, name='edit_pronostic'),
    path('pronostic/<int:pk>/delete/', views.delete_pronostic, name='delete_pronostic'),
    path('toggle_theme/', views.toggle_theme, name='toggle_theme'),

    # URLs pour le profil public, suivi, notifications, etc.
    path('profile/<str:username>/', views.public_profile, name='public_profile'),
    path('profile/<str:username>/follow/', views.follow_user, name='follow_user'),
    path('profile/<str:username>/unfollow/', views.unfollow_user, name='unfollow_user'),
    path('notifications/', views.notification_list, name='notification_list'),
    path('followed-feed/', views.followed_pronostics_feed, name='followed_pronostics_feed'),

    # L'URL de votre nouvelle page promo
    path('promo-codes/', views.promo_codes_view, name='promo_codes'),
]

# Ces lignes pour servir les fichiers statiques et médias sont correctes
# et doivent rester dans le fichier d'URLs principal.
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
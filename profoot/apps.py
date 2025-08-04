from django.apps import AppConfig

class ProfootConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'profoot'

    def ready(self):
        # Importez vos signaux ici pour qu'ils soient enregistrés au démarrage de l'application
        import profoot.signals
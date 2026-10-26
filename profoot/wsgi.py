"""
WSGI config for profoot project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'profoot.settings')

application = get_wsgi_application()

# Sur Vercel, il n'y a pas d'étape de migration séparée : avec AUTO_MIGRATE=1, les tables
# sont créées/mises à jour au démarrage de l'application (migrate est idempotent).
if os.environ.get('AUTO_MIGRATE') == '1':
    try:
        from django.core.management import call_command

        call_command('migrate', interactive=False, verbosity=0)
    except Exception as exc:  # ne pas empêcher le site de démarrer
        print(f'[profoot] migrate au démarrage échoué : {exc}')

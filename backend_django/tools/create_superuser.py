import os
import sys
import secrets
from pathlib import Path

# Ensure project root in sys.path
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE','visioncare_django.settings')

try:
    import django
    django.setup()
except Exception as e:
    print('No se pudo inicializar Django:', e)
    sys.exit(2)

from vision_app.models import User

# Defaults (puedes cambiarlos luego desde /admin)
EMAIL = os.environ.get('VC_ADMIN_EMAIL', 'admin@visioncare.local')
USERNAME = os.environ.get('VC_ADMIN_USERNAME', 'admin')
FIRST = os.environ.get('VC_ADMIN_FIRST', 'Vision')
LAST = os.environ.get('VC_ADMIN_LAST', 'Admin')
PASSWORD = os.environ.get('VC_ADMIN_PASSWORD') or secrets.token_urlsafe(16)

user, created = User.objects.get_or_create(email=EMAIL, defaults={
    'username': USERNAME,
    'first_name': FIRST,
    'last_name': LAST,
    'is_staff': True,
    'is_superuser': True,
})

if created:
    user.set_password(PASSWORD)
    user.save()
    print('✅ Superusuario creado:')
    print('  Email:', EMAIL)
    print('  Usuario:', USERNAME)
    print('  Nombre:', FIRST, LAST)
    print('  Contraseña temporal:', PASSWORD)
else:
    if not user.is_superuser or not user.is_staff:
        user.is_superuser = True
        user.is_staff = True
        if PASSWORD:
            user.set_password(PASSWORD)
        user.save()
        print('✅ Usuario existente promovido a superusuario.')
    else:
        print('ℹ️  El superusuario ya existía. Sin cambios.')
    print('  Email:', user.email)
    print('  Usuario:', user.username)
    if PASSWORD:
        print('  Contraseña (actualizada si se indicó):', PASSWORD)

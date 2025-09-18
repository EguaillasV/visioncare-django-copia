import os
import sys
from pprint import pprint
from pathlib import Path

# Ensure project root (the folder containing manage.py) is on sys.path
CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[1]  # backend_django/
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE','visioncare_django.settings')

try:
    import django
    django.setup()
except Exception as e:
    print('Failed to setup Django:', e)
    sys.exit(2)

from django.conf import settings
from django.db import connection
import socket
import psycopg2
import certifi

print('Resolved DATABASES[default]:')
pprint(settings.DATABASES.get('default'))

print('\nAttempting DB connection and simple query...')
try:
    with connection.cursor() as c:
        c.execute('SELECT current_database(), version()')
        row = c.fetchone()
        print('Connected to:', row[0])
        print('Server version:', row[1])
    print('SUCCESS: Database connection OK')
    sys.exit(0)
except Exception as e:
    import traceback
    print('ERROR during DB check (Django connection):', e)
    print(' repr:', repr(e))
    if hasattr(e, 'args'):
        print(' args:', e.args)
    traceback.print_exc()
    
    # Try raw psycopg2 connection with detailed parameters
    cfg = settings.DATABASES.get('default', {})
    host = cfg.get('HOST')
    name = cfg.get('NAME')
    user = cfg.get('USER')
    password = cfg.get('PASSWORD')
    port = cfg.get('PORT') or 5432
    sslmode = (cfg.get('OPTIONS') or {}).get('sslmode', 'require')
    sslrootcert = (cfg.get('OPTIONS') or {}).get('sslrootcert') or certifi.where()

    print('\nDNS resolution for host:', host)
    try:
        print(socket.getaddrinfo(host, port))
    except Exception as de:
        print(' DNS resolution error:', de)

    def try_connect(p):
        print(f"\nTrying psycopg2.connect to {host}:{p} db={name} sslmode={sslmode}")
        try:
            conn = psycopg2.connect(
                host=host,
                dbname=name,
                user=user,
                password=password,
                port=p,
                sslmode=sslmode,
                sslrootcert=sslrootcert,
                connect_timeout=10,
            )
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
                print(' psycopg2 SELECT 1 OK')
            conn.close()
            return True
        except Exception as pe:
            print(' psycopg2 error:', pe)
            print(' repr:', repr(pe))
            print(' args:', getattr(pe, 'args', None))
            return False

    ok = try_connect(port)
    if not ok:
        # Try Supabase pooled port
        try_connect(6543)
    
    sys.exit(1)

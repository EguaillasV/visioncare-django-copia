#!/usr/bin/env python3
"""
Script para configurar Supabase con VisionCare Django

Mejoras:
- Soporta contraseñas con caracteres especiales (p. ej. @, $, :, /) auto-codificándolas.
- Usa urllib.parse para parsear la URL de conexión de forma robusta.
- Actualiza .env con DATABASE_URL codificada y variables individuales legibles.
"""
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, quote, unquote

def _sanitize_connection_string(cs: str) -> tuple[str, str, str, int | None, str, str]:
    """Devuelve (conn_sanitized, user, password_raw, host, port, dbname).

    - Si la contraseña contiene '@' sin codificar (u otros reservados), la codifica.
    - Mantiene el resto intacto.
    """
    cs = cs.strip()
    if not cs.startswith('postgresql://'):
        raise ValueError("La connection string debe empezar con 'postgresql://'")

    # Separamos esquema y el resto
    scheme, rest = cs.split('://', 1)
    # Separar auth de host usando el ÚLTIMO '@' (lo anterior puede estar en contraseña)
    if '@' not in rest:
        raise ValueError("Formato inválido: falta '@' separando credenciales y host")
    auth_part, host_part = rest.rsplit('@', 1)
    if ':' not in auth_part:
        raise ValueError("Formato inválido: credenciales deben ser 'usuario:contraseña'")

    user, password_raw = auth_part.split(':', 1)
    # Codificar por completo la contraseña (ningún caracter es 'safe')
    password_enc = quote(password_raw, safe='')
    rest_sanitized = f"{user}:{password_enc}@{host_part}"
    conn_sanitized = f"{scheme}://{rest_sanitized}"

    # Parsear con urlsplit ahora que está saneada
    parts = urlsplit(conn_sanitized)
    host = parts.hostname or ''
    port = parts.port
    # path viene como '/dbname'
    dbname = (parts.path or '/').lstrip('/') or 'postgres'

    return conn_sanitized, unquote(parts.username or user), password_raw, host, port, dbname


def update_env_with_supabase(connection_string):
    """Actualiza el .env con detalles de Supabase (soporta contraseñas con '@')."""
    env_path = Path('.env')

    try:
        conn_sanitized, user, password_raw, host, port, dbname = _sanitize_connection_string(connection_string)
    except Exception as e:
        print(f"❌ Connection string inválida: {e}")
        return False
    
    # Leer .env actual
    if env_path.exists():
        with open(env_path, 'r') as f:
            content = f.read()
    else:
        content = ""
    
    # Actualizar DATABASE_URL (usar la versión saneada/codificada)
    if 'DATABASE_URL=' in content:
        content = re.sub(r'DATABASE_URL=.*', f'DATABASE_URL={conn_sanitized}', content)
    else:
        content += f'\nDATABASE_URL={conn_sanitized}\n'
    
    # Actualizar variables individuales (útil para debug y otras herramientas)
    updates = {
        'DB_NAME': dbname,
        'DB_USER': user,
        'DB_PASSWORD': password_raw,
        'DB_HOST': host,
        'DB_PORT': str(port or 5432),
    }
    
    for key, value in updates.items():
        if f'{key}=' in content:
            content = re.sub(f'{key}=.*', f'{key}={value}', content)
        else:
            content += f'{key}={value}\n'
    
    # Escribir contenido actualizado
    with open(env_path, 'w') as f:
        f.write(content)

    # Mostrar resumen (sin exponer la contraseña)
    shown_conn = conn_sanitized.replace(password_raw, '****') if password_raw else conn_sanitized
    print("✅ .env actualizado correctamente!")
    print(f"🔗 DATABASE_URL: {shown_conn}")
    print(f"📊 Database: {dbname}")
    print(f"🏠 Host: {host}")
    print(f"👤 User: {user}")
    return True

def test_connection():
    """Probar conexión a la base de datos a través de Django."""
    try:
        import django
        from django.conf import settings
        from django.db import connection
        
        # Setup Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'visioncare_django.settings')
        django.setup()
        
        # Test connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        
        if result:
            print("✅ ¡Conexión a Supabase exitosa!")
            return True
        else:
            print("❌ Error en la conexión")
            return False
            
    except Exception as e:
        # Imprimir detalles útiles del error
        print("❌ Error conectando a la base de datos:")
        print("   Tipo:", type(e).__name__)
        print("   Detalle:", e)
        if hasattr(e, 'args'):
            print("   Args:", e.args)
        return False

if __name__ == "__main__":
    print("🐘 Configurador de Supabase para VisionCare")
    print("=" * 50)
    
    connection_string = input("📝 Pega tu Supabase connection string: ").strip()
    
    if not connection_string.startswith('postgresql://'):
        print("❌ La connection string debe empezar con 'postgresql://' (p.ej. postgresql://usuario:contraseña@host:5432/postgres)")
        exit(1)
    
    if update_env_with_supabase(connection_string):
        print("\n🧪 Probando conexión...")
        if test_connection():
            print("\n🎉 ¡Supabase configurado correctamente!")
            print("🚀 Puedes ejecutar las migraciones ahora:")
            print("   python manage.py migrate")
        else:
            print("\n⚠️  Configuración guardada, pero hay problemas de conexión")
            print("   Verifica tu connection string y permisos de red")
    else:
        print("❌ Error actualizando la configuración")
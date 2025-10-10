#!/usr/bin/env python3
"""
Script para configurar Supabase con VisionCare Django
"""
import os
import re
from pathlib import Path

def update_env_with_supabase(connection_string):
    """Update .env file with Supabase connection details"""
    env_path = Path('.env')
    
    # Parse connection string
    # Format: postgresql://postgres:password@db.xxx.supabase.co:5432/postgres
    pattern = r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/([^?]+)'
    match = re.match(pattern, connection_string)
    
    if not match:
        print("❌ Invalid connection string format")
        return False
    
    user, password, host, port, dbname = match.groups()
    
    # Read current .env
    if env_path.exists():
        with open(env_path, 'r') as f:
            content = f.read()
    else:
        content = ""
    
    # Update DATABASE_URL
    if 'DATABASE_URL=' in content:
        content = re.sub(r'DATABASE_URL=.*', f'DATABASE_URL={connection_string}', content)
    else:
        content += f'\nDATABASE_URL={connection_string}\n'
    
    # Update individual settings
    updates = {
        'DB_NAME': dbname,
        'DB_USER': user,
        'DB_PASSWORD': password,
        'DB_HOST': host,
        'DB_PORT': port
    }
    
    for key, value in updates.items():
        if f'{key}=' in content:
            content = re.sub(f'{key}=.*', f'{key}={value}', content)
        else:
            content += f'{key}={value}\n'
    
    # Write updated content
    with open(env_path, 'w') as f:
        f.write(content)
    
    print("✅ .env file updated successfully!")
    print(f"📊 Database: {dbname}")
    print(f"🏠 Host: {host}")
    print(f"👤 User: {user}")
    return True

def test_connection():
    """Test database connection"""
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
        print(f"❌ Error conectando a la base de datos: {e}")
        return False

if __name__ == "__main__":
    print("🐘 Configurador de Supabase para VisionCare")
    print("=" * 50)
    
    connection_string = input("📝 Pega tu Supabase connection string: ").strip()
    
    if not connection_string.startswith('postgresql://'):
        print("❌ La connection string debe empezar con 'postgresql://'")
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
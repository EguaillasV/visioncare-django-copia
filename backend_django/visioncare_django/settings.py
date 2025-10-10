"""
Django settings for VisionCare project.
Eye disease detection web application.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables explicitly from backend_django/.env
load_dotenv(BASE_DIR / '.env')

# Helpers to parse env
def _csv_env(name: str, default_list: list[str] | None = None) -> list[str]:
    raw = os.getenv(name, '').strip()
    if not raw:
        return default_list or []
    return [x.strip() for x in raw.split(',') if x.strip()]

def _bool_env(name: str, default: bool) -> bool:
    return str(os.getenv(name, '1' if default else '0')).strip().lower() in ('1', 'true', 'yes')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-visioncare-secret-key-change-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = _bool_env('DEBUG', True)

# Hosts permitidos: lee de .env (coma-separado); fallback a valores de desarrollo
_default_hosts = ['localhost', '127.0.0.1', '0.0.0.0', '*']
ALLOWED_HOSTS = _csv_env('ALLOWED_HOSTS', _default_hosts)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt',
    
    # Local apps
    'vision_app',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'visioncare_django.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'visioncare_django.wsgi.application'

# Database Configuration
# ONLY Supabase/PostgreSQL via DATABASE_URL (sin fallback a SQLite)
from urllib.parse import urlparse, unquote

database_url = os.getenv('DATABASE_URL')
if not database_url:
    raise RuntimeError("DATABASE_URL es obligatorio (PostgreSQL/Supabase) y no está definido en .env")

parsed = urlparse(database_url)
if parsed.scheme not in ('postgres', 'postgresql'):
    raise RuntimeError(f"DATABASE_URL debe usar postgres/postgresql, recibido: {parsed.scheme}")

SSL_REQUIRE = str(os.getenv('DB_SSL_REQUIRE', 'true')).lower() in ('1', 'true', 'yes')

USERNAME = unquote(parsed.username or '')
PASSWORD = unquote(parsed.password or '')
DB_NAME = (parsed.path or '/').lstrip('/') or 'postgres'
HOST = parsed.hostname or 'localhost'
PORT = str(parsed.port or '5432')

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': DB_NAME,
        'USER': USERNAME,
        'PASSWORD': PASSWORD,
        'HOST': HOST,
        'PORT': PORT,
        **({'OPTIONS': {'sslmode': 'require'}} if SSL_REQUIRE else {}),
    }
}

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FileUploadParser',
    ]
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    
    'JTI_CLAIM': 'jti',
    
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

# CORS Configuration (leer desde .env)
# CORS_ALLOWED_ORIGINS acepta URLs con esquema (http/https) y puerto
_default_cors = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOWED_ORIGINS = _csv_env('CORS_ALLOWED_ORIGINS', _default_cors)

# Permitir todos los orígenes (útil en desarrollo). Cambia a 0/false en producción
CORS_ALLOW_ALL_ORIGINS = _bool_env('CORS_ALLOW_ALL_ORIGINS', True)

CORS_ALLOW_CREDENTIALS = True

# CSRF trusted origins (important cuando usas HTTPS y subdominios)
CSRF_TRUSTED_ORIGINS = _csv_env('CSRF_TRUSTED_ORIGINS', [])

CORS_ALLOW_HEADERS = [
    'accept',
    'authorization',
    'content-type',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]


# Custom User Model
AUTH_USER_MODEL = 'vision_app.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Media files (User uploaded content)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# OpenAI removed

# File Upload Settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10MB

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'debug.log',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# VisionCare ONNX / AI settings
# Default model directory inside app; can be overridden with VC_ONNX_MODEL(S)
VC_ONNX_DEFAULT_DIR = os.path.join(BASE_DIR, 'vision_app', 'onnx_models')
# Fusion thresholds for cataract probability
VC_P_CATARACT_HIGH = float(os.getenv('VC_P_CATARACT_HIGH', '0.75'))
VC_P_CATARACT_MID = float(os.getenv('VC_P_CATARACT_MID', '0.55'))

# Base site URL for building absolute links (used by adapters)
SITE_URL = os.getenv('SITE_URL', '').strip()

# Storage backend selection (media vs supabase)
VC_STORAGE = os.getenv('VC_STORAGE', 'media').strip().lower()
if VC_STORAGE in ('supabase', 'supabase_storage'):
    # Use custom storage backend for ImageField files
    # New-style setting for Django 4.2+ to ensure default_storage points to Supabase
    STORAGES = {
        'default': {
            'BACKEND': 'vision_app.adapters.storage.supabase_django_storage.SupabaseDjangoStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }
    # Backward compatibility if some code still reads this setting
    DEFAULT_FILE_STORAGE = 'vision_app.adapters.storage.supabase_django_storage.SupabaseDjangoStorage'

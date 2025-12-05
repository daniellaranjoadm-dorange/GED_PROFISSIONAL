"""
Django settings for ged project – versão profissional otimizada para Railway.
"""

from pathlib import Path
import os
from dotenv import load_dotenv
import dj_database_url

# ======================
# BASE
# ======================

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent.parent

# ======================
# SEGURANÇA
# ======================

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

DEBUG = os.environ.get("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".railway.app",
    "dorange.com.br",
    "www.dorange.com.br",
]


CSRF_TRUSTED_ORIGINS = [
    "https://*.railway.app",
    "https://dorange.com.br",
    "https://www.dorange.com.br",
    "http://dorange.com.br",
    "http://www.dorange.com.br",
]


# Segurança avançada – apenas quando DEBUG=False
# Segurança extra desativada temporariamente para diagnosticar redirects em produção.
# Depois que o sistema estiver estável, reativamos com calma.
if not DEBUG:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

    SECURE_SSL_REDIRECT = False

    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False


# ======================
# APPS
# ======================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps locais
    'apps.documentos',
    'apps.contas',
    'apps.solicitacoes',
    'apps.dashboard',
]

# ======================
# MIDDLEWARE
# ======================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    # Whitenoise para Railway
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    # Middleware de RBAC
    'apps.contas.middleware.RBACMiddleware',
]

ROOT_URLCONF = 'ged.urls'

# ======================
# TEMPLATES
# ======================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.contas.context_processors.user_config',
            ],
        },
    },
]

WSGI_APPLICATION = 'ged.wsgi.application'

# ======================
# BANCO DE DADOS - Local = SQLite / Produção = Railway PostgreSQL
# ======================

if DEBUG:
    print("💻 MODO DESENVOLVIMENTO → Usando SQLite local")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    print("🚀 PRODUÇÃO → PostgreSQL Railway")
    DATABASES = {
        "default": dj_database_url.parse(
            os.getenv("DATABASE_URL"),
            conn_max_age=600,
            ssl_require=True
        )
    }


# ======================
# VALIDAÇÃO DE SENHAS
# ======================

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ======================
# LOCALIZAÇÃO
# ======================

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

# ======================
# ARQUIVOS ESTÁTICOS
# ======================

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
WHITENOISE_USE_FINDERS = True

# ======================
# ARQUIVOS DE MÍDIA
# ======================
# IMPORTANTE: Railway NÃO mantém arquivos persistentes.
# Use MEDIA somente em modo DEBUG=True (ambiente local)

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

if not DEBUG:
    # Aviso interno – não usar media em produção
    print("⚠ MEDIA_ROOT está ativo, mas Railway não armazena arquivos permanentemente.")

# ======================
# AUTENTICAÇÃO
# ======================

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

AUTH_USER_MODEL = 'contas.Usuario'

# ======================
# EMAIL
# ======================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.office365.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_PASSWORD")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# ======================
# PADRÕES
# ======================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

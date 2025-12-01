"""
Django settings for ged project.
"""

from pathlib import Path
import os
import dj_database_url  # Adicionado para Railway

BASE_DIR = Path(__file__).resolve().parent.parent

# ======================
# CONFIGURAÇÕES GERAIS
# ======================

SECRET_KEY = 'django-insecure-#7tyz9j=!2&1^7-nhal^1=1zv(y0u9@57*#36mcfit@*mpb=ws'

DEBUG = False  # Importante para Railway

ALLOWED_HOSTS = ["*", ".railway.app"]

CSRF_TRUSTED_ORIGINS = [
    "https://*.railway.app"
]

# ======================
# APLICATIVOS
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
# MIDDLEWARE + WHITENOISE
# ======================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    # Whitenoise para servir arquivos estáticos no Railway
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'apps.contas.middleware.RBACMiddleware',
]

ROOT_URLCONF = 'ged.urls'

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
# BANCO DE DADOS (RAILWAY)
# ======================

DATABASES = {
    "default": dj_database_url.config(
        default=f"postgresql://{os.environ.get('DB_USER', 'geduser')}:{os.environ.get('DB_PASSWORD', 'gedpassword123')}@{os.environ.get('DB_HOST', 'localhost')}/{os.environ.get('DB_NAME', 'ged')}",
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
# ARQUIVOS ESTÁTICOS (Railway)
# ======================

STATIC_URL = '/static/'
STATICFILES_DIRS = [ BASE_DIR / 'static' ]
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

# ======================
# ARQUIVOS DE MÍDIA
# ======================

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

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
EMAIL_HOST_USER = "daniel.laranjo@ecovix.com"
EMAIL_HOST_PASSWORD = "Dada1606917838@"
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# ======================
# PADRÕES
# ======================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

"""
Django settings for ged project.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# SEGURANÃ‡A
# ============================================================
SECRET_KEY = 'django-insecure-#7tyz9j=!2&1^7-nhal^1=1zv(y0u9@57*#36mcfit@*mpb=ws'
DEBUG = True
ALLOWED_HOSTS = []


# ============================================================
# APLICAÃ‡Ã•ES INSTALADAS
# ============================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'apps.documentos',
    'apps.contas',          # <<==== ADICIONADO AGORA
]


# ============================================================
# MIDDLEWARE
# ============================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ============================================================
# URLS / TEMPLATES
# ============================================================
ROOT_URLCONF = 'ged.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',

        # Onde estÃ¡ seu login.html futurista
        'DIRS': [
            BASE_DIR / "templates"
        ],

        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'ged.wsgi.application'


# ============================================================
# BANCO DE DADOS
# ============================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ============================================================
# VALIDAÃ‡ÃƒO DE SENHA
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ============================================================
# IDIOMA E TIMEZONE
# ============================================================
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True
USE_TZ = True


# ============================================================
# ARQUIVOS ESTÃTICOS E MÃDIA
# ============================================================
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ============================================================
# AUTENTICAÃ‡ÃƒO
# ============================================================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'

AUTH_USER_MODEL = 'contas.Usuario'   # <-- ADICIONE ISTO

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



# ============================================================
# PADRÃ•ES
# ============================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# === Bloco adicionado automaticamente pelo script de reorganizaÃ§Ã£o ===
# Ajustes de BASE_DIR, TEMPLATES, STATIC, MEDIA e ROOT_URLCONF
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent

try:
    # Garante que os templates principais apontem para BASE_DIR / "templates"
    TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']
except Exception:
    # Se TEMPLATES nÃ£o estiver no formato esperado, nÃ£o quebra o settings
    pass

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

ROOT_URLCONF = 'ged.urls'

# RecomendaÃ§Ãµes de autenticaÃ§Ã£o:
# LOGIN_URL = 'contas:login'
# LOGIN_REDIRECT_URL = '/'
# LOGOUT_REDIRECT_URL = '/'

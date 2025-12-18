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

# Railway fica atrás de proxy/edge
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Segurança “suave” enquanto estabiliza
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
    "whitenoise.runserver_nostatic",  # antes de staticfiles

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Terceiros
    "storages",

    # Apps locais
    "apps.documentos",
    "apps.contas",
    "apps.solicitacoes",
    "apps.dashboard",
]

# ======================
# MIDDLEWARE
# ======================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    "apps.contas.middleware.RBACMiddleware",
]

ROOT_URLCONF = "ged.urls"
WSGI_APPLICATION = "ged.wsgi.application"

# ======================
# TEMPLATES
# ======================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.contas.context_processors.user_config",
            ],
        },
    },
]

# ======================
# BANCO DE DADOS
# ======================

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if DEBUG or not DATABASE_URL:
    print("MODO DESENVOLVIMENTO -> SQLite local")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    print("PRODUCAO -> PostgreSQL Railway")
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }

# ======================
# SENHAS
# ======================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ======================
# LOCALIZAÇÃO
# ======================

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ======================
# STATIC (WhiteNoise)
# ======================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# só adiciona STATICFILES_DIRS se existir a pasta "static"
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    STATICFILES_DIRS = [STATIC_DIR]
else:
    STATICFILES_DIRS = []

# evita 500/manifest faltando
WHITENOISE_MANIFEST_STRICT = False

# em produção, WhiteNoise serve do STATIC_ROOT (via collectstatic lembrando)
WHITENOISE_USE_FINDERS = DEBUG

# ======================
# MEDIA + STORAGE (Django 5.x)
# ======================

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Variáveis no Railway (você já tem AWS_* lá)
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("R2_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY") or os.environ.get("R2_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME") or os.environ.get("R2_BUCKET_NAME")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL") or os.environ.get("R2_ENDPOINT_URL")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "auto")

if not DEBUG:
    # STATIC sem manifest (mais robusto)
    STORAGES = {
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
        "default": {
            # fallback seguro: se faltar env, não derruba o deploy
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
    }

    # Se tiver tudo do R2/AWS configurado, MEDIA vai pro R2
    if all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME, AWS_S3_ENDPOINT_URL]):
        STORAGES["default"] = {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "endpoint_url": AWS_S3_ENDPOINT_URL,
                "access_key": AWS_ACCESS_KEY_ID,
                "secret_key": AWS_SECRET_ACCESS_KEY,
                "region_name": AWS_S3_REGION_NAME,
                "addressing_style": "path",
                "signature_version": "s3v4",
                "querystring_auth": True,  # bucket privado (URL assinada)
            },
        }
        print("MEDIA -> Cloudflare R2 (S3 compat)")
    else:
        print("AVISO: R2/AWS envs incompletas. MEDIA ficou local (nao persistente).")
else:
    # DEBUG: tudo local
    STORAGES = {
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    }

# ======================
# AUTENTICAÇÃO
# ======================

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
AUTH_USER_MODEL = "contas.Usuario"

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
# LOGGING
# ======================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}

# ======================
# PADRÕES
# ======================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

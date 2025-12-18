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

# Em produção, Railway geralmente fica atrás de proxy/edge
# (isso ajuda Django a entender HTTPS via proxy quando você ativar coisas de segurança depois)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Segurança avançada – mantida “suave” para não quebrar enquanto estabiliza
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
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",

    # (Opcional, recomendado) evita conflito do runserver com static quando usa WhiteNoise
    "whitenoise.runserver_nostatic",

    "django.contrib.staticfiles",

    # Terceiros (storage/media)
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

    # WhiteNoise (static)
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",

    # Middleware de RBAC
    "apps.contas.middleware.RBACMiddleware",
]

ROOT_URLCONF = "ged.urls"

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

WSGI_APPLICATION = "ged.wsgi.application"

# ======================
# BANCO DE DADOS
# Local = SQLite / Produção = Railway PostgreSQL
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
# VALIDAÇÃO DE SENHAS
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
# ARQUIVOS ESTÁTICOS (WhiteNoise)
# ======================

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# MUITO IMPORTANTE:
# evita 500 se faltar entrada no manifest (ex: admin/css/base.css)
WHITENOISE_MANIFEST_STRICT = False

# Em geral pode ficar True (ajuda durante dev),
# mas o WhiteNoise usa mais o collectstatic em produção.
WHITENOISE_USE_FINDERS = True

# ======================
# ARQUIVOS DE MÍDIA (local dev / produção via R2)
# ======================

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ======================
# STORAGE (Django 5.2+)
# - staticfiles -> WhiteNoise
# - default (MEDIA) -> local em DEBUG / R2 em produção (se envs existirem)
# ======================

# Sempre define staticfiles de forma consistente
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    # default será definido abaixo
}

# Credenciais R2 (produção)
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")

if not DEBUG:
    print("AVISO: Producao ativa. MEDIA local nao e persistente no Railway.")

    # Se faltar qualquer env, não derruba o deploy: cai para storage local
    if all([R2_BUCKET_NAME, R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        STORAGES["default"] = {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": R2_BUCKET_NAME,
                "endpoint_url": R2_ENDPOINT_URL,
                "access_key": R2_ACCESS_KEY_ID,
                "secret_key": R2_SECRET_ACCESS_KEY,
                "region_name": "auto",
                "addressing_style": "path",
                "signature_version": "s3v4",
                # bucket privado + URL assinada
                "querystring_auth": True,
            },
        }
        print("MEDIA -> Cloudflare R2 (S3 compat)")
    else:
        STORAGES["default"] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
        print("AVISO: R2 envs incompletas. MEDIA ficou local (nao persistente).")
else:
    # DEBUG = storage local
    STORAGES["default"] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

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
# LOGGING (ajuda a ver traceback no Railway)
# ======================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
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

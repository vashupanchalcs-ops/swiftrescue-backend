"""
SwiftRescue — Django Settings
ambulance_tracker/settings.py
"""

from pathlib import Path
import importlib.util
import os

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() == "true"


def env_list(name, default=""):
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]

# ─── Security ─────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-your-secret-key-here")
# Local development remains convenient while Render never exposes Django's debug pages by default.
DEBUG = env_bool("DJANGO_DEBUG", not bool(os.getenv("RENDER")))
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")

# ─── Installed Apps ───────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "channels",
    "ambulance",
    "bookings",
    "hospitals",
]

# Daphne optional fallback: enable only when explicitly requested.
if env_bool("USE_DAPHNE", False) and importlib.util.find_spec("daphne") is not None:
    INSTALLED_APPS.insert(0, "daphne")

# ─── Middleware ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ─── CORS ─────────────────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", DEBUG)
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")
render_external_url = os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
if render_external_url and render_external_url not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(render_external_url)

# ─── URLs ─────────────────────────────────────────────────────────────────────
ROOT_URLCONF = "ambulance_tracker.urls"
WSGI_APPLICATION = "ambulance_tracker.wsgi.application"
ASGI_APPLICATION = "ambulance_tracker.asgi.application"

# ─── Templates ────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ─── Database ─────────────────────────────────────────────────────────────────
# Render supplies its managed PostgreSQL connection as a single DATABASE_URL.
# SQLite remains only for local development without a configured database.
database_url = os.getenv("DATABASE_URL", "").strip()
if database_url:
    DATABASES = {
        "default": dj_database_url.parse(database_url, conn_max_age=600),
    }
elif os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB", ""),
            "USER": os.getenv("POSTGRES_USER", ""),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Channels + Redis-ready layer (fallback: in-memory)
REDIS_URL = os.getenv("REDIS_URL", "").strip()
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

# Celery queue (Redis preferred)
CELERY_BROKER_URL = REDIS_URL or os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# ─── Cache (OTP storage) ──────────────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "swiftrescue-cache",
    }
}

# ─── Email — Gmail SMTP ───────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com").strip()
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").strip().lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").strip().lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "").strip()
# Gmail app passwords are often copied as "abcd efgh ijkl mnop".
# SMTP expects the raw 16-character token, so accept either pasted form.
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "").strip().replace(" ", "")
if EMAIL_USE_SSL:
    EMAIL_USE_TLS = False
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "15"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER).strip()

# ─── Password Validators ──────────────────────────────────────────────────────
# Django 6.0 settings key
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── Internationalisation ─────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE     = "Asia/Kolkata"
USE_I18N      = True
USE_TZ        = True

# ─── Static / Media ───────────────────────────────────────────────────────────
STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL   = "/media/"
MEDIA_ROOT  = BASE_DIR / "media"

if importlib.util.find_spec("whitenoise") is not None:
    MIDDLEWARE.insert(2, "whitenoise.middleware.WhiteNoiseMiddleware")
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ─── Default Primary Key ──────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── REST Framework ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ─── Google Maps (Directions/Geocode) ───────────────────────────────────────
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()

# ─── Voice/SMS Intake Integrations ───────────────────────────────────────────
DIRECT_CALL_HOTLINE_NUMBER = os.getenv("DIRECT_CALL_HOTLINE_NUMBER", "8882128534").strip()
VOICE_PROVIDER = os.getenv("VOICE_PROVIDER", "direct").strip().lower()  # direct | exotel
OPENCAGE_API_KEY = os.getenv("OPENCAGE_API_KEY", "").strip()
GOOGLE_SPEECH_API_KEY = os.getenv("GOOGLE_SPEECH_API_KEY", "").strip()
VOICE_SMS_DEFAULT_COUNTRY = os.getenv("VOICE_SMS_DEFAULT_COUNTRY", "India").strip()
EXOTEL_API_KEY = os.getenv("EXOTEL_API_KEY", "").strip()
EXOTEL_API_TOKEN = os.getenv("EXOTEL_API_TOKEN", "").strip()
EXOTEL_SID = os.getenv("EXOTEL_SID", "").strip()
EXOTEL_SUBDOMAIN = os.getenv("EXOTEL_SUBDOMAIN", "").strip()

SMS_PROVIDER = os.getenv("SMS_PROVIDER", "msg91").strip().lower()  # msg91
MSG91_AUTH_KEY = os.getenv("MSG91_AUTH_KEY", "").strip()
MSG91_SENDER = os.getenv("MSG91_SENDER", "SWIFTR").strip()
MSG91_ROUTE = os.getenv("MSG91_ROUTE", "4").strip()

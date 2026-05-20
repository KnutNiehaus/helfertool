"""
Django settings for Helfertool running on Azure Web App
"""
import os
from pathlib import Path
from .settings import *

# Override base settings for Azure

# Security
DEBUG = os.getenv("DEBUG", "False") == "True"
SECRET_KEY = os.getenv("SECRET_KEY")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

# HTTPS enforcement
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"

# Proxy headers
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Database configuration
if os.getenv("DATABASE_URL"):
    import dj_database_url
    DATABASES = {
        "default": dj_database_url.config(default=os.getenv("DATABASE_URL"))
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "helfertool"),
            "USER": os.getenv("DB_USER"),
            "PASSWORD": os.getenv("DB_PASSWORD"),
            "HOST": os.getenv("DB_HOST"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }

# Static files - Azure stores in /home/site/wwwroot/staticfiles
STATIC_ROOT = Path("/home/site/wwwroot/staticfiles")
STATIC_URL = "/static/"
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# Media files - use Azure Blob Storage (optional)
MEDIA_ROOT = Path("/home/site/wwwroot/media")
MEDIA_URL = "/media/"

# Temporary files
TMP_ROOT = Path("/tmp/helfertool")
TMP_ROOT.mkdir(parents=True, exist_ok=True)

# Celery configuration for Azure
# CELERY_BROKER_URL = os.getenv(
#    "CELERY_BROKER_URL",
#    "amqp://guest:guest@127.0.0.1:5672//"
#)
# CELERY_RESULT_BACKEND = "django-db"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Caching - use Azure Cache for Redis (optional)
if os.getenv("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": os.getenv("REDIS_URL"),
        },
        "select2": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "select2_cache",
        },
        "locks": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "locks_cache",
        },
    }

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

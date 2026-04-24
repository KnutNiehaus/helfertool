"""
Django settings for Helfertool running on Azure Web App

This settings module is designed for deployment on Azure App Service (Linux).
It overrides the base settings with Azure-specific configurations.
"""

import os
import sys
from pathlib import Path

# Import all base settings first
from .settings import *  # noqa: F401, F403

# Override settings for Azure deployment

# ============================================================================
# SECURITY SETTINGS
# ============================================================================

# Use environment variable for debug mode (default: False)
DEBUG = os.getenv("DEBUG", "False").lower() in ["true", "1", "yes"]

# Secret key from environment (REQUIRED)
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "CHANGEME":
    print("ERROR: SECRET_KEY environment variable must be set and not 'CHANGEME'")
    sys.exit(1)

# Allowed hosts from environment
ALLOWED_HOSTS_ENV = os.getenv("ALLOWED_HOSTS", "localhost")
ALLOWED_HOSTS = [host.strip() for host in ALLOWED_HOSTS_ENV.split(",")]

# ============================================================================
# HTTPS/SSL SECURITY (Always enabled for production)
# ============================================================================

# Enforce HTTPS in production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Handle X-Forwarded-Proto header from Azure Load Balancer
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Secure cookies
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
LANGUAGE_COOKIE_SECURE = not DEBUG

# CSRF trusted origins for Azure Web App
CSRF_TRUSTED_ORIGINS = ALLOWED_HOSTS

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# Support both DATABASE_URL and individual connection parameters
if os.getenv("DATABASE_URL"):
    # Using DATABASE_URL format (e.g., from Azure)
    # Format: postgresql://user:password@host:port/database
    import dj_database_url
    
    DATABASES = {
        "default": dj_database_url.config(
            default=os.getenv("DATABASE_URL"),
            conn_max_age=600,  # Connection pooling
        )
    }
else:
    # Using individual environment variables
    db_engine = os.getenv("DB_ENGINE", "postgresql")
    db_backend = f"django.db.backends.{db_engine}"
    
    DATABASES = {
        "default": {
            "ENGINE": db_backend,
            "NAME": os.getenv("DB_NAME", "helfertool"),
            "USER": os.getenv("DB_USER", "helfertool"),
            "PASSWORD": os.getenv("DB_PASSWORD"),
            "HOST": os.getenv("DB_HOST"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "OPTIONS": {
                "connect_timeout": 10,
                "sslmode": "require" if os.getenv("DB_SSL", "true").lower() != "false" else "prefer",
            },
            "CONN_MAX_AGE": 600,  # Connection pooling for 10 minutes
        }
    }

# ============================================================================
# STATIC FILES & MEDIA STORAGE
# ============================================================================

# Static files are served by Azure Web App
# In production, use Azure Storage Blob Container
if os.getenv("AZURE_STORAGE_ACCOUNT_NAME"):
    # Using Azure Blob Storage for static files
    try:
        from storages.backends.azure_storage import AzureStorage
        
        class StaticAzureStorage(AzureStorage):
            account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
            account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
            azure_container = "staticfiles"
            expiration_secs = None
        
        class MediaAzureStorage(AzureStorage):
            account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
            account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
            azure_container = "media"
            expiration_secs = None
        
        STATIC_URL = f"https://{os.getenv('AZURE_STORAGE_ACCOUNT_NAME')}.blob.core.windows.net/staticfiles/"
        MEDIA_URL = f"https://{os.getenv('AZURE_STORAGE_ACCOUNT_NAME')}.blob.core.windows.net/media/"
        
        STATICFILES_STORAGE = "helfertool.settings_azure.StaticAzureStorage"
        DEFAULT_FILE_STORAGE = "helfertool.settings_azure.MediaAzureStorage"
    except ImportError:
        print("WARNING: django-storages not installed. Falling back to local storage.")
        STATIC_ROOT = Path("/home/site/wwwroot/staticfiles")
        STATIC_URL = "/static/"
        MEDIA_ROOT = Path("/home/site/wwwroot/media")
        MEDIA_URL = "/media/"
else:
    # Local file storage (simpler setup)
    STATIC_ROOT = Path("/home/site/wwwroot/staticfiles")
    STATIC_URL = "/static/"
    MEDIA_ROOT = Path("/home/site/wwwroot/media")
    MEDIA_URL = "/media/"

# Create directories if they don't exist
STATIC_ROOT.mkdir(parents=True, exist_ok=True)
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

# Temporary files
TMP_ROOT = Path("/tmp/helfertool")
TMP_ROOT.mkdir(parents=True, exist_ok=True)

# ============================================================================
# CACHING
# ============================================================================

# Use Azure Redis Cache if available, otherwise use database cache
if os.getenv("REDIS_URL"):
    # Using Azure Redis Cache
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": os.getenv("REDIS_URL"),
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
                "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
                "IGNORE_EXCEPTIONS": True,
            }
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
else:
    # Using database cache (default)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
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

# ============================================================================
# CELERY / BACKGROUND TASKS
# ============================================================================

# Configure Celery based on environment
celery_broker = os.getenv("CELERY_BROKER_URL")
if celery_broker:
    # Use configured broker (Redis, RabbitMQ, Azure Service Bus, etc.)
    CELERY_BROKER_URL = celery_broker
else:
    # Disable Celery: run tasks synchronously (simple setup)
    # This is suitable for smaller deployments without complex background tasks
    print("WARNING: CELERY_BROKER_URL not set. Running Celery tasks synchronously.")
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# Always use database for Celery results
CELERY_RESULT_BACKEND = "django-db"
CELERY_RESULT_EXTENDED = True
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ============================================================================
# LOGGING
# ============================================================================

# Enhanced logging for production
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
        "json": {
            "()" : "logging.Formatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "level": "INFO",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/tmp/helfertool/django.log",
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 5,
            "formatter": "verbose",
            "level": "INFO",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "helfertool": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ============================================================================
# EMAIL CONFIGURATION (Optional)
# ============================================================================

# Email backend for sending mails
if os.getenv("EMAIL_BACKEND") == "sendgrid":
    EMAIL_BACKEND = "sendgrid_backend.SendgridBackend"
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
elif os.getenv("EMAIL_HOST"):
    # Standard SMTP configuration
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ["true", "1", "yes"]
    EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in ["true", "1", "yes"]
else:
    # Console backend for development
    if DEBUG:
        EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

EMAIL_FROM = os.getenv("EMAIL_FROM", "helfertool@localhost")
DEFAULT_FROM_EMAIL = EMAIL_FROM
SERVER_EMAIL = EMAIL_FROM

# ============================================================================
# HELFERTOOL-SPECIFIC SETTINGS
# ============================================================================

# Configuration file location
HELFERTOOL_CONFIG_FILE = os.getenv("HELFERTOOL_CONFIG_FILE", "/home/site/helfertool.yaml")

# Language and timezone
LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "de")
TIME_ZONE = os.getenv("TIME_ZONE", "Europe/Berlin")

# LaTeX for badge generation (pdflatex path)
BADGE_PDFLATEX = os.getenv("BADGE_PDFLATEX", "/usr/bin/pdflatex")

# ============================================================================
# COMPRESSION
# ============================================================================

# Enable compression for production
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = not DEBUG  # Offline compression in production

# ============================================================================
# ADDITIONAL AZURE-SPECIFIC SETTINGS
# ============================================================================

# App Insights integration (optional)
if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    try:
        import logging.config
        from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter
        
        # Configure Azure Monitor logging (advanced)
        # This requires: pip install azure-monitor-opentelemetry-exporter
    except ImportError:
        pass  # App Insights instrumentation not installed

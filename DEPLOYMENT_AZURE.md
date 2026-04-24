# Azure Web App Deployment Guide for Helfertool

This guide provides step-by-step instructions for deploying Helfertool as an Azure Web App instead of a containerized application.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Azure Resources Setup](#azure-resources-setup)
3. [GitHub Secrets Configuration](#github-secrets-configuration)
4. [Environment Variables](#environment-variables)
5. [Database Configuration](#database-configuration)
6. [Background Tasks (Celery)](#background-tasks-celery)
7. [Static Files & Media Storage](#static-files--media-storage)
8. [Application Startup](#application-startup)
9. [Troubleshooting](#troubleshooting)
10. [Post-Deployment Steps](#post-deployment-steps)

---

## Prerequisites

- Azure Subscription (with sufficient quota)
- GitHub repository access
- Basic familiarity with Azure Portal
- Local deployment testing (optional but recommended)

---

## Azure Resources Setup

### Step 1: Create Resource Group

1. Go to [Azure Portal](https://portal.azure.com)
2. Click **+ Create a resource**
3. Search for **Resource Group**
4. Click **Create**
5. Fill in:
   - **Subscription:** Select your subscription
   - **Resource group name:** `helfertool-rg`
   - **Region:** Choose closest to your users (e.g., `West Europe` for Germany)
6. Click **Review + Create → Create**

### Step 2: Create App Service Plan

1. In the Resource Group, click **+ Create a resource**
2. Search for **App Service Plan**
3. Click **Create**
4. Fill in:
   - **Name:** `helfertool-plan`
   - **Resource Group:** `helfertool-rg`
   - **Operating System:** Linux
   - **Region:** Same as resource group
   - **SKU and size:** 
     - Dev/Test: **B2** (1.75 GB RAM, $0.122/hour)
     - Production: **P1V2** (3.5 GB RAM, $0.202/hour)
5. Click **Review + Create → Create**

### Step 3: Create Web App

1. In the Resource Group, click **+ Create a resource**
2. Search for **Web App**
3. Click **Create**
4. Fill in:
   - **Name:** `Helfertool-WebApp` (must be globally unique)
   - **Resource Group:** `helfertool-rg`
   - **Runtime stack:** `Python 3.12`
   - **Region:** Same as above
   - **App Service Plan:** `helfertool-plan`
5. Click **Review + Create → Create**

### Step 4: Configure Application Settings

1. Go to your newly created Web App
2. Click **Settings → Configuration**
3. Add the following **Application settings** (see [Environment Variables](#environment-variables) section for values):

| Key | Value | Note |
|-----|-------|------|
| `DJANGO_SETTINGS_MODULE` | `helfertool.settings` | |
| `ALLOWED_HOSTS` | `Helfertool-WebApp.azurewebsites.net` | Replace with your domain |
| `SECRET_KEY` | `(generate below)` | See Secret Key section |
| `DEBUG` | `False` | **Always False in production** |
| `HELFERTOOL_CONFIG_FILE` | `/home/site/helfertool.yaml` | Configuration file path |

4. Click **Save**

### Step 5: Create Database

Choose one:

#### Option A: Azure Database for PostgreSQL (Recommended)

1. In Resource Group, click **+ Create a resource**
2. Search for **Azure Database for PostgreSQL - Flexible Server**
3. Click **Create**
4. Fill in:
   - **Server name:** `helfertool-db`
   - **Resource Group:** `helfertool-rg`
   - **Admin username:** `helferadmin`
   - **Password:** (generate strong password)
   - **Region:** Same as above
   - **Pricing tier:** Burstable, `Standard_B1ms`
5. After creation, go to **Settings → Networking**
   - Set **Public access:** Allow
   - Add **Firewall rule:** Allow Azure services to access
   - Add your IP address for local testing
6. Get connection string from **Settings → Connection strings**

#### Option B: Azure Database for MySQL

Similar process; MySQL is also supported.

---

## GitHub Secrets Configuration

1. Go to your GitHub repository
2. Click **Settings → Secrets and variables → Actions**
3. Click **New repository secret**

Add these secrets:

### 1. Azure Publish Profile

1. Go to Web App → **Settings → General**
2. Click **Download publish profile** (top right)
3. Open the XML file in a text editor
4. Create secret:
   - **Name:** `AZUREAPPSERVICE_PUBLISHPROFILE_<ID>`
   - **Value:** (paste entire XML content)

Use the ID shown in your workflow file.

### 2. Database Connection String

```
AZUREAPPSERVICE_DATABASE_URL=postgresql://user:password@host:5432/dbname
```

Or as environment variables:

```
DB_USER=helferadmin
DB_PASSWORD=<your_password>
DB_HOST=helfertool-db.postgres.database.azure.com
DB_NAME=helfertool
```

---

## Environment Variables

Configure these in Azure Portal (**Configuration → Application settings**):

### Django Settings

```bash
DJANGO_SETTINGS_MODULE=helfertool.settings
SECRET_KEY=<generate_secure_key_below>
ALLOWED_HOSTS=Helfertool-WebApp.azurewebsites.net,yourdomain.com
DEBUG=False
```

### Generate Secret Key

Run locally:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Or in Django shell:

```bash
cd src
python manage.py shell
>>> from django.core.management.utils import get_random_secret_key
>>> print(get_random_secret_key())
```

### Database Configuration

```bash
# PostgreSQL
DB_ENGINE=postgresql
DB_USER=helferadmin
DB_PASSWORD=<your_password>
DB_HOST=helfertool-db.postgres.database.azure.com
DB_PORT=5432
DB_NAME=helfertool

# Or as single URL
DATABASE_URL=postgresql://helferadmin:password@helfertool-db.postgres.database.azure.com:5432/helfertool
```

### Helfertool-Specific Settings

```bash
HELFERTOOL_CONFIG_FILE=/home/site/helfertool.yaml
LANGUAGE_CODE=de
TIME_ZONE=Europe/Berlin
```

---

## Database Configuration

### Create Database Settings Module

Create `src/helfertool/settings_azure.py`:

```python
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
CELERY_BROKER_URL = os.getenv(
    "CELERY_BROKER_URL",
    "amqp://guest:guest@127.0.0.1:5672//"
)
CELERY_RESULT_BACKEND = "django-db"

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
```

### Initialize Database

After deployment, run migrations via Azure Portal:

1. Web App → **Development tools → SSH** (or use Deployment Center)
2. Navigate to application:
   ```bash
   cd /home/site/wwwroot/src
   ```
3. Run migrations:
   ```bash
   python manage.py migrate --noinput
   ```
4. Create superuser:
   ```bash
   python manage.py createsuperuser
   ```
5. Create cache table:
   ```bash
   python manage.py createcachetable
   ```
6. Load initial data (if needed):
   ```bash
   python manage.py loaddata toolsettings
   ```

---

## Background Tasks (Celery)

Helfertool uses Celery for background tasks. You have options:

### Option 1: Disable Celery (Simple Setup)

If you don't need background tasks, modify `src/helfertool/settings_azure.py`:

```python
# Disable Celery - tasks run synchronously
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
```

### Option 2: Use Azure Service Bus (Recommended)

1. Create Azure Service Bus resource
2. Install in requirements: `celery-azure-service-bus`
3. Configure in `settings_azure.py`:
   ```python
   CELERY_BROKER_URL = "azureservicebus://..."
   ```

### Option 3: Use Hosted RabbitMQ

1. Sign up for hosted RabbitMQ service (CloudAMQP, etc.)
2. Add to environment variables:
   ```bash
   CELERY_BROKER_URL=amqp://user:pass@host:5672/vhost
   ```

### Option 4: Use Redis (Simplest)

1. Create Azure Cache for Redis
2. Configure:
   ```bash
   CELERY_BROKER_URL=redis://:password@host:6379
   REDIS_URL=redis://:password@host:6379
   ```

---

## Static Files & Media Storage

### Configure Blob Storage (Optional but Recommended)

1. Create Azure Storage Account in Resource Group
2. Create container `staticfiles` and `media`
3. Get connection string from **Access keys**
4. Install: `pip install django-storages azure-storage-blob`
5. Update `settings_azure.py`:

```python
from storages.backends.azure_storage import AzureStorage

# Static files
STATIC_URL = "https://<storage-account>.blob.core.windows.net/staticfiles/"
DEFAULT_FILE_STORAGE = "storages.backends.azure_storage.AzureStorage"
STATICFILES_STORAGE = "storages.backends.azure_storage.AzureStorage"

# Azure Storage settings
AZURE_ACCOUNT_NAME = os.getenv("AZURE_ACCOUNT_NAME")
AZURE_ACCOUNT_KEY = os.getenv("AZURE_ACCOUNT_KEY")
AZURE_CONTAINER = "staticfiles"
```

### Local File Storage (Simpler)

Files stored in `/home/site/wwwroot/media`. Add to settings:

```python
MEDIA_ROOT = Path("/home/site/wwwroot/media")
MEDIA_URL = "/media/"
```

---

## Application Startup

### Startup Command Configuration

Web App → **Settings → General → Startup command**:

```bash
gunicorn --chdir src helfertool.wsgi:application --bind 0.0.0.0:8000 --workers 4 --worker-class sync --timeout 60
```

Or add to `web.config` (auto-generated):

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <location path="application_root">
    <system.webServer>
      <handlers>
        <add name="PythonHandler" path="*" verb="*" modules="httpPlatformHandler" scriptProcessor="D:\Program Files\Python312\python.exe" resourceType="Unspecified" requireAccess="Script" />
      </handlers>
      <httpPlatform processPath="D:\Program Files\Python312\Scripts\gunicorn.exe" arguments="--chdir src --workers 4 helfertool.wsgi:application" stdoutLogEnabled="true" stdoutLogFile="\\?\%home%\LogFiles\stdout" startupTimeLimit="60" />
    </system.webServer>
  </location>
</configuration>
```

### Deployment Slots (Optional)

For zero-downtime deployments:

1. Web App → **Deployment slots**
2. Click **Add slot**
3. Create "staging" slot
4. Deploy to staging first, then swap to production

---

## Troubleshooting

### Check Logs

1. Web App → **Monitoring → Log stream**
2. Or download logs: **Deployment center → Logs**

### Common Issues

#### "ModuleNotFoundError: No module named 'django'"

**Solution:** Dependencies not installed. Check:
- `src/requirements.txt` and `src/requirements_prod.txt` exist
- Workflow runs `pip install -r src/requirements.txt -r src/requirements_prod.txt`
- Python version matches (3.12)

#### "psycopg2 import error"

**Solution:** Add to `requirements_prod.txt`:
```
psycopg2-binary~=3.3.2
```

#### "ALLOWED_HOSTS error"

**Solution:** Ensure `ALLOWED_HOSTS` environment variable includes your domain:
```
Helfertool-WebApp.azurewebsites.net,yourdomain.com
```

#### "SECRET_KEY is invalid or None"

**Solution:** Set `SECRET_KEY` in Application settings. Generate with:
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

#### Static files not loading (404 errors)

**Solution:**
1. Run `python manage.py collectstatic --noinput` locally to test
2. Ensure workflow uploads static files
3. Check `STATIC_ROOT` and `STATIC_URL` configuration

#### Database connection refused

**Solution:**
1. Test connection locally
2. Verify firewall rules allow Web App to Database
3. Check credentials: `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`
4. Ensure database exists

#### CSRF cookie errors

**Solution:** Add to settings:
```python
CSRF_TRUSTED_ORIGINS = ["https://Helfertool-WebApp.azurewebsites.net"]
```

---

## Post-Deployment Steps

### 1. Configure Custom Domain (Optional)

1. Web App → **Settings → Custom domains**
2. Click **Add custom domain**
3. Verify ownership via DNS TXT record
4. Add SSL certificate

### 2. Set Up HTTPS

1. Web App → **Settings → TLS/SSL settings**
2. Enable **HTTPS only**
3. Add certificate (auto-managed or upload)

### 3. Configure Monitoring

1. Web App → **Insights**
2. Enable Application Insights
3. Set up alerts for:
   - High error rate
   - High response time
   - Low availability

### 4. Database Backups

PostgreSQL:
1. Go to Database server
2. Click **Backups**
3. Set retention policy (default: 7 days)

### 5. Celery Tasks (if enabled)

For background workers, use **Azure Container Instances** or **App Service** multiple instances with worker configuration.

### 6. Create Admin User

If not created during deployment:

```bash
# Via Azure Portal SSH
cd /home/site/wwwroot/src
python manage.py createsuperuser
```

### 7. Test Application

1. Navigate to `https://Helfertool-WebApp.azurewebsites.net`
2. Log in with admin credentials
3. Test key features:
   - Event creation
   - User management
   - Badge generation (if LaTeX installed)
   - File uploads

---

## Environment Variables Summary

**Required:**
- `DJANGO_SETTINGS_MODULE=helfertool.settings`
- `SECRET_KEY=<secure_key>`
- `ALLOWED_HOSTS=<your-domain>`
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`

**Optional:**
- `DEBUG=False` (default if not set)
- `LANGUAGE_CODE=de`
- `TIME_ZONE=Europe/Berlin`
- `CELERY_BROKER_URL` (if using Celery)
- `REDIS_URL` (if using Redis cache)
- `HELFERTOOL_CONFIG_FILE=/home/site/helfertool.yaml`

---

## Additional Resources

- [Azure Web Apps Python Documentation](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python)
- [Django Deployment Documentation](https://docs.djangoproject.com/en/5.0/howto/deployment/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Helfertool GitHub Repository](https://github.com/helfertool/helfertool)

---

## Support & Questions

For issues specific to Helfertool configuration, see:
- [Helfertool Documentation](https://www.helfertool.org)
- [GitHub Issues](https://github.com/helfertool/helfertool/issues)

For Azure-specific issues:
- [Azure Support](https://support.microsoft.com/en-us/azure)
- [Azure App Service Troubleshooting](https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-common-app-service-errors)

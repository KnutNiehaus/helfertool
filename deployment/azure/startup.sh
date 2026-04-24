#!/bin/bash

# Startup script for Helfertool on Azure Web App (Linux)
# This script handles initialization, migrations, and app startup

set -e  # Exit on error

# Color output for logging
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'  # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# ============================================================================
# STEP 1: Change to application directory
# ============================================================================

cd /home/site/wwwroot

log_info "Working directory: $(pwd)"
log_info "Python version: $(python --version)"
log_info "Gunicorn version: $(gunicorn --version)"

# ============================================================================
# STEP 2: Verify environment variables
# ============================================================================

log_info "Checking required environment variables..."

if [ -z "$DJANGO_SETTINGS_MODULE" ]; then
    log_error "DJANGO_SETTINGS_MODULE is not set"
    exit 1
fi

if [ -z "$SECRET_KEY" ]; then
    log_error "SECRET_KEY is not set"
    exit 1
fi

if [ -z "$ALLOWED_HOSTS" ]; then
    log_warn "ALLOWED_HOSTS is not set, using default"
fi

log_info "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
log_info "ALLOWED_HOSTS: $ALLOWED_HOSTS"
log_info "DEBUG: ${DEBUG:-False}"

# ============================================================================
# STEP 3: Create necessary directories
# ============================================================================

log_info "Creating necessary directories..."

mkdir -p /home/site/wwwroot/staticfiles
mkdir -p /home/site/wwwroot/media
mkdir -p /tmp/helfertool
mkdir -p /home/site/logs

log_info "Directories created successfully"

# ============================================================================
# STEP 4: Run Django migrations
# ============================================================================

log_info "Running Django migrations..."

cd /home/site/wwwroot/src

python manage.py migrate --noinput || {
    log_error "Migration failed"
    exit 1
}

log_info "Migrations completed successfully"

# ============================================================================
# STEP 5: Create cache table (for Django cache framework)
# ============================================================================

log_info "Creating cache table..."

python manage.py createcachetable 2>/dev/null || true  # May already exist

log_info "Cache table created (or already exists)"

# ============================================================================
# STEP 6: Collect static files
# ============================================================================

if [ "${SKIP_COLLECTSTATIC:-false}" != "true" ]; then
    log_info "Collecting static files..."
    
    python manage.py collectstatic --noinput --clear || {
        log_error "collectstatic failed"
        exit 1
    }
    
    log_info "Static files collected successfully"
else
    log_info "Skipping collectstatic (SKIP_COLLECTSTATIC=true)"
fi

# ============================================================================
# STEP 7: Compress static files (optional)
# ============================================================================

if [ "${COMPRESS_OFFLINE:-true}" = "true" ]; then
    log_info "Compressing static files..."
    
    python manage.py compress --force 2>/dev/null || true
    
    log_info "Static files compressed (or compression skipped)"
fi

# ============================================================================
# STEP 8: Create superuser (optional, for first-time setup)
# ============================================================================

if [ "${CREATE_SUPERUSER:-false}" = "true" ]; then
    if [ -z "$DJANGO_SUPERUSER_USERNAME" ] || [ -z "$DJANGO_SUPERUSER_PASSWORD" ] || [ -z "$DJANGO_SUPERUSER_EMAIL" ]; then
        log_warn "DJANGO_SUPERUSER_* environment variables not set, skipping superuser creation"
    else
        log_info "Creating superuser..."
        
        python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
END
    fi
fi

# ============================================================================
# STEP 9: Load initial data (optional)
# ============================================================================

if [ "${LOAD_INITIAL_DATA:-true}" = "true" ]; then
    log_info "Loading initial data..."
    
    python manage.py loaddata toolsettings 2>/dev/null || true
    
    log_info "Initial data loaded (or already exists)"
fi

# ============================================================================
# STEP 10: Start Gunicorn
# ============================================================================

log_info "Starting Gunicorn..."

# Determine number of workers based on available CPU cores
if [ -z "$GUNICORN_WORKERS" ]; then
    GUNICORN_WORKERS=$((2 * $(nproc --all) + 1))
    log_info "GUNICORN_WORKERS not set, auto-configured to: $GUNICORN_WORKERS"
else
    log_info "GUNICORN_WORKERS: $GUNICORN_WORKERS"
fi

# Gunicorn configuration
GUNICORN_BIND="${GUNICORN_BIND:-0.0.0.0:8000}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
GUNICORN_MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-1000}"

log_info "Gunicorn configuration:"
log_info "  Bind: $GUNICORN_BIND"
log_info "  Workers: $GUNICORN_WORKERS"
log_info "  Timeout: $GUNICORN_TIMEOUT"
log_info "  Max requests: $GUNICORN_MAX_REQUESTS"

# Change back to application root
cd /home/site/wwwroot

# Start Gunicorn
exec gunicorn \
    --bind "$GUNICORN_BIND" \
    --workers "$GUNICORN_WORKERS" \
    --worker-class sync \
    --timeout "$GUNICORN_TIMEOUT" \
    --max-requests "$GUNICORN_MAX_REQUESTS" \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --chdir src \
    helfertool.wsgi:application

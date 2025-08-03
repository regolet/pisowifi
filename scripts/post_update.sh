#!/bin/bash
# Post-update script for Orange Pi deployment

echo "Running post-update tasks..."

# Restart the PISOWifi service
if command -v supervisorctl &> /dev/null; then
    echo "Restarting PISOWifi service via Supervisor..."
    sudo supervisorctl restart pisowifi
elif command -v systemctl &> /dev/null; then
    echo "Restarting PISOWifi service via systemd..."
    sudo systemctl restart pisowifi
else
    echo "Warning: No service manager found. Please restart manually."
fi

# Run any database migrations
cd /opt/pisowifi
source venv/bin/activate
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Clear any caches
python manage.py clear_cache 2>/dev/null || true

echo "Post-update tasks completed!"
#!/bin/sh
# Entrypoint unificado — decide entre web e worker baseado em SERVICE_TYPE
if [ "$SERVICE_TYPE" = "worker" ]; then
    echo ">>> Iniciando Celery worker..."
    exec celery -A worker.celery_app worker --loglevel=info --concurrency=1
else
    echo ">>> Iniciando gunicorn web..."
    exec gunicorn "app:create_app()" --bind "0.0.0.0:${PORT:-5050}" --workers 2 --timeout 120
fi

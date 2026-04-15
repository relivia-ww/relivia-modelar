web: gunicorn "app:create_app()" --bind 0.0.0.0:${PORT:-5050} --workers 2 --timeout 120
worker: celery -A worker.celery_app worker --loglevel=info --concurrency=1

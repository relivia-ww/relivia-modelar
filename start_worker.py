"""
Script de entrada para o servico worker.
Roda via: python start_worker.py
"""
import os
print(">>> Iniciando Celery worker...", flush=True)
os.execvp("celery", [
    "celery", "-A", "worker.celery_app", "worker",
    "--loglevel=info", "--concurrency=1"
])

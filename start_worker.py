"""
Inicia o worker Celery.
Execute em um terminal separado:
  python start_worker.py
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    from worker.celery_app import celery
    argv = [
        "worker",
        "--loglevel=info",
        f"--concurrency={os.environ.get('MAX_CONCURRENT_JOBS', '2')}",
        "--pool=solo",  # Windows não suporta fork — usa solo (single-thread)
    ]
    celery.worker_main(argv)

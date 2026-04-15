from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

celery = Celery(
    "relivia_modelar",
    broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    include=["worker.tasks"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_time_limit=600,         # 10 min — DrissionPage + Claude pode demorar
    task_soft_time_limit=540,
    worker_max_tasks_per_child=10,
    worker_concurrency=int(os.environ.get("MAX_CONCURRENT_JOBS", 2)),
)

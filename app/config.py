import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-inseguro")
    _base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _db_url = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(_base_dir, 'instance', 'relivia_modelar.db')}"
    )
    # Railway retorna postgres://, SQLAlchemy precisa de postgresql+psycopg2://
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql+psycopg2://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    CLAUDE_API_KEY = os.environ.get("CLAUDE_API_KEY", "")

    AGENTE_CLONE_SCRIPT = os.environ.get(
        "AGENTE_CLONE_SCRIPT",
        r"C:/Users/user/Desktop/Obsidian Supremo/Otimizacao de escala/agente-clone/agente_clone.py"
    )
    AGENTE_CLONE_RUNS_BASE = os.environ.get(
        "AGENTE_CLONE_RUNS_BASE",
        "C:/projetos/relivia-modelar/runs"
    )
    MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", 2))

    # Chave de criptografia Fernet derivada do SECRET_KEY
    @staticmethod
    def fernet_key():
        import base64, hashlib
        raw = os.environ.get("SECRET_KEY", "dev").encode()
        digest = hashlib.sha256(raw).digest()
        return base64.urlsafe_b64encode(digest)


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}

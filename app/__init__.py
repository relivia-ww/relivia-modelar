import os
from flask import Flask
from .extensions import db, login_manager
from .config import config


def create_app(env_name: str = "default") -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[env_name])

    # Garante que instance/ existe e ajusta URI do SQLite para caminho absoluto
    os.makedirs(app.instance_path, exist_ok=True)
    db_path = os.path.join(app.instance_path, "relivia_modelar.db")
    if "sqlite:///" in app.config.get("SQLALCHEMY_DATABASE_URI", ""):
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

    # Extensões
    db.init_app(app)
    login_manager.init_app(app)

    # Health check (Railway)
    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    # Blueprints
    from .routes.auth import auth_bp
    from .routes.onboarding import onboarding_bp
    from .routes.modelar import modelar_bp
    from .routes.editor import editor_bp
    from .routes.publicar import publicar_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(modelar_bp)
    app.register_blueprint(editor_bp)
    app.register_blueprint(publicar_bp)

    # Cria tabelas na primeira execução + migração de colunas faltando
    with app.app_context():
        db.create_all()
        _run_migrations(db)

    return app


def _run_migrations(db):
    """Adiciona colunas que podem estar faltando no banco existente."""
    from sqlalchemy import text, inspect
    engine = db.engine
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("clone_jobs")}

    migrations = [
        ("out_dir",    "ALTER TABLE clone_jobs ADD COLUMN out_dir TEXT"),
        ("html_path",  "ALTER TABLE clone_jobs ADD COLUMN html_path TEXT"),
        ("error_msg",  "ALTER TABLE clone_jobs ADD COLUMN error_msg TEXT"),
        ("commit_url", "ALTER TABLE clone_jobs ADD COLUMN commit_url TEXT"),
        ("published_url", "ALTER TABLE clone_jobs ADD COLUMN published_url TEXT"),
        ("images_count", "ALTER TABLE clone_jobs ADD COLUMN images_count INTEGER DEFAULT 0"),
    ]

    with engine.connect() as conn:
        for col, sql in migrations:
            if col not in cols:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception:
                    pass

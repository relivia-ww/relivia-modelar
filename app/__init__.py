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

    # Cria tabelas na primeira execução
    with app.app_context():
        db.create_all()

    return app

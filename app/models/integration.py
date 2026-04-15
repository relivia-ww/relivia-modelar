from datetime import datetime
from cryptography.fernet import Fernet
from ..extensions import db
from ..config import Config


def _fernet():
    return Fernet(Config.fernet_key())


class Integration(db.Model):
    __tablename__ = "integrations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # GitHub
    github_token_enc = db.Column(db.Text, nullable=True)
    github_repo = db.Column(db.String(200), nullable=True)   # "owner/repo"
    github_branch = db.Column(db.String(100), default="main")

    # Vercel
    vercel_token_enc = db.Column(db.Text, nullable=True)
    vercel_project_id = db.Column(db.String(200), nullable=True)
    vercel_domain = db.Column(db.String(300), nullable=True)  # ex: meusite.vercel.app

    user = db.relationship("User", back_populates="integration")

    # ── helpers de criptografia ──────────────────────────────────────

    def set_github_token(self, token: str):
        self.github_token_enc = _fernet().encrypt(token.encode()).decode()

    def get_github_token(self) -> str:
        if not self.github_token_enc:
            return ""
        return _fernet().decrypt(self.github_token_enc.encode()).decode()

    def set_vercel_token(self, token: str):
        self.vercel_token_enc = _fernet().encrypt(token.encode()).decode()

    def get_vercel_token(self) -> str:
        if not self.vercel_token_enc:
            return ""
        return _fernet().decrypt(self.vercel_token_enc.encode()).decode()

    @property
    def github_configured(self) -> bool:
        return bool(self.github_token_enc and self.github_repo)

    @property
    def vercel_configured(self) -> bool:
        return bool(self.vercel_token_enc and self.vercel_project_id)

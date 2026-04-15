import uuid
from datetime import datetime
from ..extensions import db


class CloneJob(db.Model):
    __tablename__ = "clone_jobs"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    url = db.Column(db.Text, nullable=False)
    page_type = db.Column(db.String(20), default="produto")   # "produto" | "advertorial"
    nome_pasta = db.Column(db.String(100), nullable=True)

    # Status: queued | running | done | error | published
    status = db.Column(db.String(20), default="queued")
    progress_msg = db.Column(db.Text, nullable=True)

    out_dir = db.Column(db.Text, nullable=True)    # path absoluto: runs/<id>/
    html_path = db.Column(db.Text, nullable=True)  # path absoluto: runs/<id>/index.html
    images_count = db.Column(db.Integer, default=0)

    published_url = db.Column(db.Text, nullable=True)
    commit_url = db.Column(db.Text, nullable=True)
    error_msg = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship("User", back_populates="jobs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "page_type": self.page_type,
            "nome_pasta": self.nome_pasta,
            "status": self.status,
            "progress_msg": self.progress_msg,
            "images_count": self.images_count,
            "published_url": self.published_url,
            "commit_url": self.commit_url,
            "error_msg": self.error_msg,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

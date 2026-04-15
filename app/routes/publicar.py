from pathlib import Path
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from ..extensions import db
from ..models.clone_job import CloneJob
from ..services.github_service import GitHubService
from ..services.vercel_service import VercelService

publicar_bp = Blueprint("publicar", __name__)


def _get_job(job_id: str) -> CloneJob:
    return CloneJob.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()


@publicar_bp.route("/publicar/<job_id>", methods=["POST"])
@login_required
def publicar(job_id):
    """
    1. Commita index.html + imagens no GitHub
    2. Aguarda deploy Vercel ficar READY
    3. Retorna { ok, commit_url, published_url }
    """
    job = _get_job(job_id)

    if job.status not in ("done", "published"):
        return jsonify({"error": f"Job em status '{job.status}' — aguarde terminar"}), 400

    integration = current_user.integration
    if not integration or not integration.github_configured:
        return jsonify({"error": "Configure GitHub nas integrações antes de publicar"}), 400

    out_dir = Path(job.out_dir) if job.out_dir else None
    if not out_dir or not out_dir.exists():
        return jsonify({"error": "Diretório de output não encontrado"}), 400

    # ── 1. GitHub commit ────────────────────────────────────────────
    try:
        gh = GitHubService(
            token=integration.get_github_token(),
            repo=integration.github_repo,
            branch=integration.github_branch,
        )
        result = gh.commit_job_files(nome_pasta=job.nome_pasta, out_dir=out_dir)
    except Exception as e:
        return jsonify({"error": f"Erro ao commitar no GitHub: {e}"}), 502

    commit_url = result.get("commit_url", "")

    # ── 2. Vercel polling ────────────────────────────────────────────
    published_url = ""
    vercel_status = "skipped"

    if integration.vercel_configured:
        try:
            vc = VercelService(
                token=integration.get_vercel_token(),
                project_id=integration.vercel_project_id,
            )
            deploy = vc.poll_until_ready(timeout=180)
            vercel_status = deploy.get("status", "UNKNOWN")
            if deploy.get("url"):
                published_url = f"{deploy['url']}/{job.nome_pasta}/"
        except Exception as e:
            vercel_status = f"ERROR: {e}"

    # ── 3. Atualiza job ──────────────────────────────────────────────
    job.status = "published"
    job.commit_url = commit_url
    job.published_url = published_url
    db.session.commit()

    return jsonify({
        "ok": True,
        "committed": result.get("committed", 0),
        "skipped_images": result.get("skipped", 0),
        "commit_url": commit_url,
        "vercel_status": vercel_status,
        "published_url": published_url,
    })


@publicar_bp.route("/publicar/<job_id>/status")
@login_required
def status(job_id):
    """Retorna status de publicação do job (para polling do frontend)."""
    job = _get_job(job_id)
    return jsonify({
        "status": job.status,
        "published_url": job.published_url or "",
        "commit_url": job.commit_url or "",
    })

import os
import re
from flask import Blueprint, render_template, redirect, url_for, request, jsonify, flash, send_file
from flask_login import login_required, current_user
from pathlib import Path
from ..extensions import db
from ..models.clone_job import CloneJob

modelar_bp = Blueprint("modelar", __name__)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", text.lower()).strip("-")[:40]


@modelar_bp.route("/dashboard")
@login_required
def dashboard():
    jobs = current_user.jobs.order_by(CloneJob.created_at.desc()).limit(50).all()
    integration = current_user.integration
    return render_template("dashboard.html", jobs=jobs, integration=integration)


@modelar_bp.route("/modelar", methods=["GET", "POST"])
@login_required
def new():
    integration = current_user.integration
    if not integration or not integration.github_configured:
        flash("Configure sua integração com GitHub antes de modelar.", "warning")
        return redirect(url_for("onboarding.setup"))

    if request.method == "POST":
        url = request.form.get("url", "").strip()
        page_type = request.form.get("page_type", "produto")
        nome_pasta = request.form.get("nome_pasta", "").strip()

        if not url:
            flash("Cole a URL da página que deseja modelar.", "error")
            return render_template("modelar.html")

        if not nome_pasta:
            nome_pasta = _slug(url.split("//")[-1].split("/")[0])

        job = CloneJob(
            user_id=current_user.id,
            url=url,
            page_type=page_type,
            nome_pasta=nome_pasta,
            status="queued",
            progress_msg="Na fila...",
        )
        db.session.add(job)
        db.session.commit()

        # Enfileira no Celery
        from worker.tasks import run_clone
        run_clone.delay(job.id, url, page_type, nome_pasta)

        return redirect(url_for("modelar.status", job_id=job.id))

    return render_template("modelar.html")


@modelar_bp.route("/modelar/<job_id>")
@login_required
def status(job_id):
    job = CloneJob.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()
    return render_template("modelar_status.html", job=job)


@modelar_bp.route("/modelar/<job_id>/status.json")
@login_required
def status_json(job_id):
    job = CloneJob.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()
    return jsonify(job.to_dict())


@modelar_bp.route("/modelar/<job_id>/download")
@login_required
def download(job_id):
    job = CloneJob.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()
    runs_base = Path(os.environ.get("AGENTE_CLONE_RUNS_BASE", "/app/runs"))
    html_path = runs_base / job_id / "index.html"
    if not html_path.exists():
        flash("Arquivo não encontrado.", "error")
        return redirect(url_for("modelar.status", job_id=job_id))
    return send_file(
        html_path,
        as_attachment=True,
        download_name=f"{job.nome_pasta}.html",
        mimetype="text/html",
    )


@modelar_bp.route("/modelar/<job_id>/delete", methods=["POST"])
@login_required
def delete(job_id):
    job = CloneJob.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()
    db.session.delete(job)
    db.session.commit()
    flash("Job removido.", "success")
    return redirect(url_for("modelar.dashboard"))

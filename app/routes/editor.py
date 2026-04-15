import os
from pathlib import Path
from flask import Blueprint, render_template, request, jsonify, send_file, abort, Response
from flask_login import login_required, current_user
from ..extensions import db
from ..models.clone_job import CloneJob
from ..services.gemini_service import edit_image

editor_bp = Blueprint("editor", __name__)


def _get_job(job_id: str) -> CloneJob:
    """Retorna job verificando que pertence ao usuário logado."""
    return CloneJob.query.filter_by(id=job_id, user_id=current_user.id).first_or_404()


@editor_bp.route("/editor/<job_id>")
@login_required
def editor(job_id):
    job = _get_job(job_id)
    if job.status not in ("done", "published"):
        return render_template("editor_wait.html", job=job)

    integration = current_user.integration
    vercel_domain = (integration.vercel_domain or "") if integration else ""
    return render_template("editor.html", job=job, vercel_domain=vercel_domain)


@editor_bp.route("/editor/<job_id>/preview")
@login_required
def preview(job_id):
    """Serve o index.html do job para o iframe."""
    job = _get_job(job_id)
    if not job.html_path or not Path(job.html_path).exists():
        abort(404)

    html = Path(job.html_path).read_text(encoding="utf-8", errors="replace")

    # Injeta base href para assets relativos (imagens do job)
    integration = current_user.integration
    if integration and integration.vercel_domain:
        base = f"https://{integration.vercel_domain}/{job.nome_pasta}/"
    else:
        base = f"/editor/{job_id}/asset/"

    if "<base " not in html[:500]:
        html = html.replace("<head>", f'<head>\n  <base href="{base}">', 1)
        if "<head>" not in html:
            html = f'<base href="{base}">' + html

    return Response(html, mimetype="text/html")


@editor_bp.route("/editor/<job_id>/asset/<path:filename>")
@login_required
def asset(job_id, filename):
    """Serve assets estáticos do job (imagens) via Flask."""
    job = _get_job(job_id)
    out_dir = Path(job.out_dir) if job.out_dir else None
    if not out_dir:
        abort(404)

    file_path = (out_dir / filename).resolve()
    # Segurança: garante que o arquivo está dentro do out_dir
    if not str(file_path).startswith(str(out_dir.resolve())):
        abort(403)
    if not file_path.exists():
        abort(404)

    return send_file(str(file_path))


@editor_bp.route("/editor/<job_id>/save", methods=["POST"])
@login_required
def save(job_id):
    """Salva HTML editado de volta ao disco."""
    job = _get_job(job_id)
    if not job.html_path:
        return jsonify({"error": "Job sem html_path"}), 400

    data = request.get_json(force=True) or {}
    html = data.get("html", "")
    if not html:
        return jsonify({"error": "html vazio"}), 400

    Path(job.html_path).write_text(html, encoding="utf-8")
    return jsonify({"ok": True})


@editor_bp.route("/editor/<job_id>/generate-image", methods=["POST"])
@login_required
def generate_image(job_id):
    """Gera nova versão de uma imagem via Gemini."""
    job = _get_job(job_id)
    data = request.get_json(force=True) or {}
    prompt = (data.get("prompt") or "").strip()
    image_name = (data.get("image_name") or "").strip()

    if not prompt:
        return jsonify({"error": "Prompt obrigatório"}), 400
    if not image_name:
        return jsonify({"error": "image_name obrigatório"}), 400

    out_dir = Path(job.out_dir) if job.out_dir else None
    if not out_dir:
        return jsonify({"error": "Job sem out_dir"}), 400

    image_path = (out_dir / "images" / image_name).resolve()
    if not str(image_path).startswith(str(out_dir.resolve())):
        return jsonify({"error": "Acesso negado"}), 403
    if not image_path.exists():
        return jsonify({"error": f"Imagem '{image_name}' não encontrada"}), 404

    try:
        api_key = os.environ.get("GEMINI_API_KEY", "")
        data_uri = edit_image(str(image_path), prompt, api_key)
        return jsonify({"ok": True, "data_uri": data_uri})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

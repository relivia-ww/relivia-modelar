import requests
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from ..extensions import db
from ..models.integration import Integration

onboarding_bp = Blueprint("onboarding", __name__)


@onboarding_bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def setup():
    integration = current_user.integration or Integration(user_id=current_user.id)

    if request.method == "POST":
        gh_token = request.form.get("github_token", "").strip()
        gh_repo = request.form.get("github_repo", "").strip()
        gh_branch = request.form.get("github_branch", "main").strip()
        vc_token = request.form.get("vercel_token", "").strip()
        vc_project = request.form.get("vercel_project_id", "").strip()
        vc_domain = request.form.get("vercel_domain", "").strip()

        if gh_token:
            integration.set_github_token(gh_token)
        if gh_repo:
            integration.github_repo = gh_repo
        if gh_branch:
            integration.github_branch = gh_branch
        if vc_token:
            integration.set_vercel_token(vc_token)
        if vc_project:
            integration.vercel_project_id = vc_project
        if vc_domain:
            integration.vercel_domain = vc_domain.rstrip("/")

        if not current_user.integration:
            db.session.add(integration)
            current_user.integration = integration

        db.session.commit()
        flash("Configurações salvas com sucesso!", "success")
        return redirect(url_for("modelar.dashboard"))

    return render_template("onboarding.html", integration=integration)


@onboarding_bp.route("/onboarding/test-github", methods=["POST"])
@login_required
def test_github():
    integration = current_user.integration
    if not integration or not integration.github_configured:
        return jsonify({"ok": False, "error": "GitHub não configurado"}), 400

    token = integration.get_github_token()
    repo = integration.github_repo
    branch = integration.github_branch

    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/branches/{branch}",
            headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            timeout=8,
        )
        if r.status_code == 200:
            return jsonify({"ok": True, "message": f"Repositório {repo} acessível ✅"})
        return jsonify({"ok": False, "error": f"GitHub retornou {r.status_code}: {r.json().get('message', '')}"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@onboarding_bp.route("/onboarding/test-vercel", methods=["POST"])
@login_required
def test_vercel():
    integration = current_user.integration
    if not integration or not integration.vercel_configured:
        return jsonify({"ok": False, "error": "Vercel não configurado"}), 400

    token = integration.get_vercel_token()
    project_id = integration.vercel_project_id

    try:
        r = requests.get(
            f"https://api.vercel.com/v9/projects/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
        if r.status_code == 200:
            name = r.json().get("name", project_id)
            return jsonify({"ok": True, "message": f"Projeto '{name}' acessível ✅"})
        return jsonify({"ok": False, "error": f"Vercel retornou {r.status_code}: {r.json().get('error', {}).get('message', '')}"}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

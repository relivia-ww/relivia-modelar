from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from ..extensions import db
from ..models.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("modelar.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("modelar.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            next_url = request.args.get("next") or url_for("modelar.dashboard")
            return redirect(next_url)

        flash("E-mail ou senha incorretos.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("modelar.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not email or not password:
            flash("E-mail e senha são obrigatórios.", "error")
            return render_template("auth/register.html")

        if password != confirm:
            flash("As senhas não coincidem.", "error")
            return render_template("auth/register.html")

        if len(password) < 8:
            flash("A senha deve ter pelo menos 8 caracteres.", "error")
            return render_template("auth/register.html")

        if User.query.filter_by(email=email).first():
            flash("Este e-mail já está cadastrado.", "error")
            return render_template("auth/register.html")

        user = User(email=email, name=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)
        flash("Conta criada! Configure sua integração com GitHub e Vercel.", "success")
        return redirect(url_for("onboarding.setup"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

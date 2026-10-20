from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select

from ..extensions import db, limiter, oauth
from ..forms import LoginForm
from ..models import ROLE_ADMIN, User, utcnow
from ..security import is_safe_redirect_target

bp = Blueprint("auth", __name__)


def _get_user(email):
    return db.session.execute(select(User).filter_by(email=email)).scalar_one_or_none()


def _start_session(user):
    """Log `user` in with a fresh session (drops anything set before authentication)."""
    session.clear()
    login_user(user, remember=False, fresh=True)
    session.permanent = True  # expires after PERMANENT_SESSION_LIFETIME
    user.last_login_at = utcnow()
    db.session.commit()


def _after_login_url(candidate=None):
    return candidate if is_safe_redirect_target(candidate) else url_for("admin.dashboard")


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(lambda: current_app.config["LOGIN_RATE_LIMIT"], methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()
    if request.method == "GET":
        form.next.data = request.args.get("next", "")

    if form.validate_on_submit():
        user = _get_user(form.email.data)
        if user is None:
            User.burn_password_check(form.password.data)
        if user is not None and user.active and user.check_password(form.password.data):
            _start_session(user)
            current_app.logger.info("Login: %s", user.email)
            return redirect(_after_login_url(form.next.data))

        current_app.logger.warning("Failed login for %r from %s", form.email.data[:100], request.remote_addr)
        # Same message for unknown email, wrong password and disabled account: no account enumeration.
        flash("И-мэйл эсвэл нууц үг буруу байна.", "danger")

    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
def logout():
    # POST + CSRF token: a malicious page can't log people out with a plain <img>/link.
    logout_user()
    session.clear()
    flash("Системээс амжилттай гарлаа.", "info")
    return redirect(url_for("main.index"))


@bp.route("/login/google")
def login_google():
    if not current_app.config["GOOGLE_OAUTH_ENABLED"]:
        abort(404)
    return oauth.google.authorize_redirect(url_for("auth.google_callback", _external=True))


@bp.route("/auth/google/callback")
def google_callback():
    if not current_app.config["GOOGLE_OAUTH_ENABLED"]:
        abort(404)

    try:
        token = oauth.google.authorize_access_token()
        info = token.get("userinfo") or oauth.google.userinfo(token=token)
    except Exception:  # noqa: BLE001 - any OAuth failure must fail closed
        current_app.logger.exception("Google sign-in failed")
        flash("Google-ээр нэвтрэх үед алдаа гарлаа. Дахин оролдоно уу.", "danger")
        return redirect(url_for("auth.login"))

    email = (info.get("email") or "").strip().lower()
    if not email or not info.get("email_verified"):
        flash("Google хаягийн и-мэйл баталгаажаагүй байна.", "danger")
        return redirect(url_for("auth.login"))

    user = _get_user(email)
    if user is None and email in current_app.config["ADMIN_EMAILS"]:
        # Allow-listed address signing in for the first time: provision an admin account.
        user = User(email=email, full_name=info.get("name"), role=ROLE_ADMIN, active=True)
        db.session.add(user)
        db.session.commit()
        current_app.logger.info("Provisioned admin from ADMIN_EMAILS: %s", email)

    if user is None or not user.active:
        current_app.logger.warning("Google sign-in rejected for %s", email)
        flash(f"Уучлаарай, {email} хаяг админ эрхгүй байна.", "danger")
        return redirect(url_for("main.index"))

    _start_session(user)
    flash(f"Амжилттай нэвтэрлээ: {email}", "success")
    return redirect(url_for("admin.dashboard"))

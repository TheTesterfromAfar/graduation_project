"""Application factory."""
import os
from datetime import datetime

from flask import Flask, render_template
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from . import sqlite  # noqa: F401  (registers the SQLite connection listener)
from .cli import register_cli
from .config import INSECURE_SECRET_KEYS, get_config
from .extensions import csrf, db, limiter, login_manager, migrate, oauth
from .headers import register_security_headers
from .questions import RATING_SCALE
from .services.answers import answer
from .timeutil import format_local

ERROR_PAGES = {
    400: ("Хүсэлт буруу байна", "Илгээсэн хүсэлтийг боловсруулах боломжгүй байна. Хуудсаа дахин ачаалаад үзнэ үү."),
    403: ("Хандах эрхгүй", "Танд энэ хуудсыг үзэх эрх байхгүй байна."),
    404: ("Хуудас олдсонгүй", "Таны хайсан хуудас олдсонгүй эсвэл устгагдсан байна."),
    405: ("Зөвшөөрөгдөөгүй үйлдэл", "Энэ хуудсанд ийм хүсэлт илгээх боломжгүй."),
    413: ("Өгөгдөл хэт том байна", "Оруулсан өгөгдөл зөвшөөрөгдсөн хэмжээнээс хэтэрсэн байна."),
    429: ("Хэт олон хүсэлт", "Богино хугацаанд хэт олон хүсэлт илгээлээ. Түр хүлээгээд дахин оролдоно уу."),
    500: ("Системийн алдаа", "Уучлаарай, алдаа гарлаа. Дахин оролдоно уу. Асуудал давтагдвал администраторт мэдэгдэнэ үү."),
}


def create_app(config_name=None, config_overrides=None):
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))
    if config_overrides:
        app.config.update(config_overrides)

    _check_production_settings(app)
    app.logger.setLevel(app.config["LOG_LEVEL"])
    os.makedirs(app.instance_path, exist_ok=True)

    _configure_proxy(app)
    _init_extensions(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _register_template_helpers(app)
    register_security_headers(app)
    register_cli(app)
    return app


def _check_production_settings(app):
    if app.config["APP_ENV"] != "production":
        return
    key = app.config.get("SECRET_KEY") or ""
    if key.lower() in INSECURE_SECRET_KEYS or len(key) < 32:
        raise RuntimeError(
            "SECRET_KEY is missing or too weak. Set a random value of at least 32 characters in the "
            "environment or .env, e.g.:  python -c \"import secrets; print(secrets.token_hex(32))\""
        )


def _configure_proxy(app):
    proxies = app.config["TRUSTED_PROXY_COUNT"]
    if proxies > 0:
        # Trust exactly this many reverse proxies for client IP, scheme and host.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies)


def _init_extensions(app):
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Энэ хуудсыг үзэхийн тулд нэвтэрнэ үү."
    login_manager.login_message_category = "warning"
    login_manager.session_protection = "strong"

    oauth.init_app(app)
    enabled = bool(app.config["GOOGLE_CLIENT_ID"] and app.config["GOOGLE_CLIENT_SECRET"])
    app.config["GOOGLE_OAUTH_ENABLED"] = enabled
    if enabled:
        oauth.register(
            name="google",
            overwrite=True,
            client_id=app.config["GOOGLE_CLIENT_ID"],
            client_secret=app.config["GOOGLE_CLIENT_SECRET"],
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    from . import models  # noqa: F401  (make sure every model is known to Flask-Migrate)


def _register_blueprints(app):
    from .blueprints import admin, auth, main, surveys

    app.register_blueprint(main.bp)
    app.register_blueprint(surveys.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp, url_prefix="/admin")


def _register_error_handlers(app):
    def render_error(error):
        code = getattr(error, "code", None) or 500
        if code == 500:
            db.session.rollback()
        title, message = ERROR_PAGES.get(code, ERROR_PAGES[500])
        return render_template("errors/error.html", code=code, title=title, message=message), code

    for code in ERROR_PAGES:
        app.register_error_handler(code, render_error)

    @app.errorhandler(CSRFError)
    def csrf_error(_error):
        message = ("Аюулгүй байдлын шалтгаанаар хуудасны хугацаа дууссан байна. "
                   "Хуудсаа дахин ачаалаад, дахин илгээнэ үү.")
        return render_template("errors/error.html", code=400, title="Хуудасны хугацаа дууссан", message=message), 400


def _static_version(app):
    """Cache-busting token: changes whenever the CSS/JS files change."""
    newest = 0
    for name in ("css/app.css", "js/app.js", "js/boot.js"):
        try:
            newest = max(newest, int(os.path.getmtime(os.path.join(app.static_folder, name))))
        except OSError:
            pass
    return newest or 1


def _register_template_helpers(app):
    version = _static_version(app)
    # A real Jinja global (not a context-processor value) so imported macros can use it too.
    app.jinja_env.globals["rating_scale"] = RATING_SCALE
    app.jinja_env.globals["answer"] = answer   # answer(record, field): works for columns and admin-added questions

    @app.template_filter("localtime")
    def localtime_filter(value, fmt="%Y-%m-%d %H:%M"):
        return format_local(value, app.config["APP_TIMEZONE"], fmt)

    @app.context_processor
    def inject_globals():
        return {
            "site_name": app.config["SITE_NAME"],
            "google_enabled": app.config["GOOGLE_OAUTH_ENABLED"],
            "current_year": datetime.now().year,
            "asset_version": version,
        }

from flask import Blueprint, jsonify, render_template
from sqlalchemy import text

from ..extensions import db
from ..questions import SURVEYS

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("main/index.html", surveys=SURVEYS)


@bp.route("/healthz")
def healthz():
    """Liveness/readiness probe for Docker and load balancers."""
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - any DB failure means "not ready"
        return jsonify(status="error"), 503
    return jsonify(status="ok")

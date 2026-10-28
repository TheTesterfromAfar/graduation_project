from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db, limiter
from ..forms import survey_form
from ..models import SURVEY_MODELS
from ..services.survey_store import get_surveys

bp = Blueprint("surveys", __name__)


def _survey_limit():
    # Only submissions are limited (per IP); opening the form is not.
    return limiter.limit(lambda: current_app.config["SURVEY_RATE_LIMIT"], methods=["POST"])


def _handle_survey(survey_type):
    spec = get_surveys()[survey_type]     # the questions as the admin has set them
    model = SURVEY_MODELS[survey_type]
    form = survey_form(spec)

    if form.validate_on_submit():
        if form.website.data:
            # Honeypot filled: a bot. Pretend success so it learns nothing, store nothing.
            current_app.logger.info("Honeypot triggered on %s survey from %s", survey_type, request.remote_addr)
            return redirect(url_for("surveys.success", survey_type=survey_type))

        columns = set(model.__table__.columns.keys()) - {"id", "timestamp", "extra_answers"}
        values = {name: (None if value == "" else value) for name, value in form.data.items() if name in columns}
        # Rating questions an admin added from the web have no column: keep their answers as JSON.
        extra = {q.field: form.data[q.field] for q in spec.rating_questions if q.field not in columns}
        values["extra_answers"] = extra or None
        try:
            db.session.add(model(**values))
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Could not save %s survey response", survey_type)
            flash("Уучлаарай, хариултыг хадгалах үед алдаа гарлаа. Дахин оролдоно уу.", "danger")
        else:
            return redirect(url_for("surveys.success", survey_type=survey_type))
    elif request.method == "POST":
        flash("Маягтад алдаа байна. Улаанаар тэмдэглэсэн хэсгүүдийг засаад дахин илгээнэ үү.", "danger")

    return render_template(f"surveys/{survey_type}.html", form=form, spec=spec)


@bp.route("/employer", methods=["GET", "POST"])
@_survey_limit()
def employer():
    return _handle_survey("employer")


@bp.route("/student", methods=["GET", "POST"])
@_survey_limit()
def student():
    return _handle_survey("student")


@bp.route("/success")
def success():
    survey_type = request.args.get("survey_type")
    return render_template("surveys/success.html", survey_type=survey_type if survey_type in get_surveys() else None)

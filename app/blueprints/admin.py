from datetime import datetime

from flask import (Blueprint, Response, abort, current_app, flash, redirect, render_template, request,
                   send_file, url_for)
from flask_login import current_user
from sqlalchemy import select

from ..decorators import roles_required
from ..extensions import db
from ..forms import AdminDataEditForm, AdminDataForm
from ..models import ROLE_ADMIN, ROLES, SURVEY_MODELS, AdminDataEntry
from ..questions import SURVEYS
from ..services import export, queries, stats

bp = Blueprint("admin", __name__)


@bp.before_request
def require_staff():
    """Every /admin route needs a signed-in, active staff account."""
    if not current_user.is_authenticated:
        return current_app.login_manager.unauthorized()
    if current_user.role not in ROLES:
        abort(403)


def _survey(survey_type):
    if survey_type not in SURVEYS:
        abort(404)
    return SURVEYS[survey_type], SURVEY_MODELS[survey_type]


# --------------------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------------------
@bp.route("/", strict_slashes=False)
def dashboard():
    summaries = [stats.survey_summary(spec) for spec in SURVEYS.values()]
    timeline = stats.daily_counts(current_app.config["APP_TIMEZONE"], days=14)
    peak = max([day["total"] for day in timeline] + [1])
    return render_template("admin/dashboard.html", summaries=summaries, timeline=timeline, peak=peak,
                           data_entry_count=db.session.query(AdminDataEntry).count())


# --------------------------------------------------------------------------------------
# Responses: list (search / filter / sort / paginate), detail, delete
# --------------------------------------------------------------------------------------
@bp.route("/responses/<survey_type>")
def responses(survey_type):
    spec, model = _survey(survey_type)
    filters = queries.parse_filters(request.args, spec)
    stmt = queries.build_query(model, spec, filters, current_app.config["APP_TIMEZONE"])

    page = request.args.get("page", 1, type=int)
    pagination = db.paginate(stmt, page=page, per_page=current_app.config["PAGE_SIZE"], max_per_page=100, error_out=False)
    averages = {row.id: queries.row_average(row, spec) for row in pagination.items}

    return render_template(
        "admin/responses.html",
        spec=spec,
        survey_type=survey_type,
        pagination=pagination,
        averages=averages,
        filters=filters,
        has_filters=bool(set(filters) - {"sort"}),
    )


@bp.route("/responses/<survey_type>/<int:response_id>")
def response_detail(survey_type, response_id):
    spec, model = _survey(survey_type)
    record = db.get_or_404(model, response_id)
    return render_template("admin/response_detail.html", spec=spec, survey_type=survey_type, record=record,
                           average=queries.row_average(record, spec))


@bp.route("/responses/<survey_type>/<int:response_id>/delete", methods=["POST"])
@roles_required(ROLE_ADMIN)
def response_delete(survey_type, response_id):
    _, model = _survey(survey_type)
    record = db.get_or_404(model, response_id)
    db.session.delete(record)
    db.session.commit()
    current_app.logger.info("%s deleted %s response #%s", current_user.email, survey_type, response_id)
    flash("Хариултыг устгалаа.", "success")
    return redirect(url_for("admin.responses", survey_type=survey_type))


# --------------------------------------------------------------------------------------
# Export (respects the active search / filters)
# --------------------------------------------------------------------------------------
@bp.route("/export/<survey_type>/<fmt>")
def export_responses(survey_type, fmt):
    spec, model = _survey(survey_type)
    if fmt not in ("csv", "xlsx"):
        abort(404)

    tz_name = current_app.config["APP_TIMEZONE"]
    filters = queries.parse_filters(request.args, spec)
    records = db.session.execute(queries.build_query(model, spec, filters, tz_name)).scalars().all()

    columns = spec.export_columns
    headers = [header for _, header in columns]
    rows = export.table_rows(records, columns, tz_name)
    filename = f"{survey_type}_survey_{datetime.now().strftime('%Y-%m-%d')}.{fmt}"
    current_app.logger.info("%s exported %d %s responses as %s", current_user.email, len(records), survey_type, fmt)

    if fmt == "csv":
        return Response(export.iter_csv(headers, rows), mimetype=export.CSV_MIME,
                        headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    return send_file(export.build_xlsx(headers, rows), mimetype=export.XLSX_MIME, as_attachment=True,
                     download_name=filename)


# --------------------------------------------------------------------------------------
# Admin JSON data (upload / paste / edit / delete)
# --------------------------------------------------------------------------------------
@bp.route("/data")
def data_list():
    entries = db.session.execute(select(AdminDataEntry).order_by(AdminDataEntry.timestamp.desc())).scalars().all()
    return render_template("admin/data.html", entries=entries, form=AdminDataForm())


@bp.route("/data/add", methods=["POST"])
@roles_required(ROLE_ADMIN)
def data_add():
    form = AdminDataForm()
    if form.validate_on_submit():
        db.session.add(AdminDataEntry(filename=form.filename, content=form.content))
        db.session.commit()
        flash("Өгөгдөл амжилттай нэмэгдлээ.", "success")
        return redirect(url_for("admin.data_list"))

    flash("Өгөгдөл хадгалагдсангүй. Доорх алдааг засна уу.", "danger")
    entries = db.session.execute(select(AdminDataEntry).order_by(AdminDataEntry.timestamp.desc())).scalars().all()
    return render_template("admin/data.html", entries=entries, form=form)


@bp.route("/data/<int:entry_id>/edit", methods=["GET", "POST"])
@roles_required(ROLE_ADMIN)
def data_edit(entry_id):
    entry = db.get_or_404(AdminDataEntry, entry_id)
    form = AdminDataEditForm(obj=entry)
    if form.validate_on_submit():
        entry.content = form.content.data
        db.session.commit()
        flash("Өгөгдөл амжилттай шинэчлэгдлээ.", "success")
        return redirect(url_for("admin.data_list"))
    return render_template("admin/data_edit.html", entry=entry, form=form)


@bp.route("/data/<int:entry_id>/delete", methods=["POST"])
@roles_required(ROLE_ADMIN)
def data_delete(entry_id):
    entry = db.get_or_404(AdminDataEntry, entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash("Өгөгдөл амжилттай устгагдлаа.", "success")
    return redirect(url_for("admin.data_list"))

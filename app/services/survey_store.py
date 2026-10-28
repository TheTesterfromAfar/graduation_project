"""Load and save the admin's survey edits (table `survey_configs`) and hand out the resolved surveys.

The rules live in survey_config.py (no database); this module is the thin database layer around them.
"""
from flask import current_app, g, has_app_context
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from wtforms import SelectField

from ..extensions import db
from ..forms import SURVEY_FORMS
from ..models import SURVEY_MODELS, SurveyConfig, utcnow
from ..questions import SURVEYS
from .survey_config import InfoField, resolve

_CACHE_KEY = "resolved_surveys"


def get_surveys():
    """{survey key: SurveySpec} with the admin's edits applied.

    Read from the database at most once per request. Nothing is cached between requests: Gunicorn
    runs several worker processes, and an edit has to show up in all of them at once. The table is
    tiny (one row per survey), so the extra query is negligible.

    If the table cannot be read (for example, a deploy that has not run its migration yet), the
    surveys fall back to the defaults in questions.py instead of failing every page.
    """
    if has_app_context() and _CACHE_KEY in g:
        return g.get(_CACHE_KEY)

    documents = {}
    try:
        for row in db.session.execute(select(SurveyConfig)).scalars():
            documents[row.survey_key] = row.data
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Could not read survey_configs; showing the default questions")

    surveys = {key: resolve(spec, documents.get(key)) for key, spec in SURVEYS.items()}
    if has_app_context():
        setattr(g, _CACHE_KEY, surveys)
    return surveys


def _forget():
    if has_app_context():
        g.pop(_CACHE_KEY, None)


def load_document(survey_key, lock=False):
    """The stored edits for one survey (None when it has never been edited).

    `lock=True` takes a row lock (SELECT ... FOR UPDATE on PostgreSQL) until commit, so two admins
    saving at the same moment cannot overwrite each other's change. SQLite ignores it.
    """
    stmt = select(SurveyConfig).where(SurveyConfig.survey_key == survey_key)
    if lock:
        stmt = stmt.with_for_update()
    row = db.session.execute(stmt).scalar_one_or_none()
    return row.data if row is not None else None


def save_document(survey_key, document, editor_email):
    """Store `document` for the survey and commit. Raises SQLAlchemyError if the write fails."""
    row = db.session.get(SurveyConfig, survey_key)
    if row is None:
        db.session.add(SurveyConfig(survey_key=survey_key, data=document, updated_by=(editor_email or "")[:255]))
    else:
        row.data = document
        row.updated_by = (editor_email or "")[:255]
        row.updated_at = utcnow()
    db.session.commit()
    _forget()


def reset_document(survey_key):
    """Forget every edit for the survey: it shows the defaults from questions.py again."""
    row = db.session.get(SurveyConfig, survey_key)
    if row is not None:
        db.session.delete(row)
        db.session.commit()
    _forget()


def info_fields(survey_key):
    """{name: InfoField} for the survey's fixed questions (everything except the ratings), in form order.

    Read from the form class itself, so the editor always matches forms.py: the question text, the
    dropdown choices, and the longest answer the database column accepts (PostgreSQL enforces
    VARCHAR lengths, SQLite does not).
    """
    form = SURVEY_FORMS[survey_key](formdata=None, meta={"csrf": False})
    columns = SURVEY_MODELS[survey_key].__table__.columns

    fields = {}
    for field in form:
        if field.name == "website" or field.name not in columns:   # honeypot / CSRF token
            continue
        choices = None
        if isinstance(field, SelectField):
            choices = tuple(value for value, _label in field.choices if value != "")
        fields[field.name] = InfoField(
            name=field.name,
            label=field.label.text,
            choices=choices,
            max_len=getattr(columns[field.name].type, "length", None),
        )
    return fields

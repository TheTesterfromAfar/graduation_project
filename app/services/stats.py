"""Aggregations for the admin dashboard."""
from datetime import timedelta

from sqlalchemy import func, select

from ..extensions import db
from ..models import SURVEY_MODELS, utcnow
from ..timeutil import to_local


def _count(model, since=None):
    stmt = select(func.count()).select_from(model)
    if since is not None:
        stmt = stmt.where(model.timestamp >= since)
    return db.session.execute(stmt).scalar_one()


def _round_average(total, n):
    return round(total / n, 2) if n else None


def rating_averages(model, fields):
    """{field: average or None}. NULLIF(col, 0) drops legacy zero placeholders from the mean.

    Original questions are real columns and are averaged by the database. Questions an admin added
    from the web live in the JSON column `extra_answers` and are averaged here (a few thousand
    rows at most for a survey like this, and the same approach services/majors.py already uses).
    """
    if not fields:
        return {}
    column_names = set(model.__table__.columns.keys())
    in_columns = [f for f in fields if f in column_names]
    in_json = [f for f in fields if f not in column_names]

    averages = {}
    if in_columns:
        columns = [func.avg(func.nullif(getattr(model, f), 0)).label(f) for f in in_columns]
        row = db.session.execute(select(*columns)).one()
        averages.update({f: (round(float(row[i]), 2) if row[i] is not None else None) for i, f in enumerate(in_columns)})

    if in_json:
        totals = {f: [0, 0] for f in in_json}     # field -> [sum, count]
        for stored in db.session.execute(select(model.extra_answers)).scalars():
            if not isinstance(stored, dict):
                continue
            for f in in_json:
                value = stored.get(f)
                if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                    totals[f][0] += value
                    totals[f][1] += 1
        averages.update({f: _round_average(total, n) for f, (total, n) in totals.items()})
    return averages


def distribution(model, field):
    column = getattr(model, field)
    stmt = (
        select(column, func.count().label("n"))
        .where(column.is_not(None), column != "")
        .group_by(column)
        .order_by(func.count().desc(), column)
    )
    rows = db.session.execute(stmt).all()
    total = sum(n for _, n in rows)
    return [{"value": value, "count": n, "percent": round(n * 100 / total, 1)} for value, n in rows] if total else []


def survey_summary(spec):
    model = SURVEY_MODELS[spec.key]
    now = utcnow()
    averages = rating_averages(model, spec.rating_fields)
    scored = [v for v in averages.values() if v is not None]

    groups = []
    for group in spec.rating_groups:
        groups.append({
            "title": group.title,
            "rows": [{"label": qn.short, "average": averages.get(qn.field)} for qn in group.questions],
        })

    return {
        "spec": spec,
        "total": _count(model),
        "last_7_days": _count(model, now - timedelta(days=7)),
        "last_30_days": _count(model, now - timedelta(days=30)),
        "overall_average": round(sum(scored) / len(scored), 2) if scored else None,
        "groups": groups,
        "distributions": [
            {"label": label, "rows": distribution(model, field)} for field, label in spec.distribution_fields
        ],
    }


def daily_counts(tz_name, days=14):
    """Responses per local calendar day for the last `days` days, split by survey."""
    from ..timeutil import local_day_start_utc

    today = to_local(utcnow(), tz_name).date()
    first_day = today - timedelta(days=days - 1)
    since = local_day_start_utc(first_day, tz_name)

    series = [{"date": first_day + timedelta(days=i), "employer": 0, "student": 0} for i in range(days)]
    by_date = {entry["date"]: entry for entry in series}

    for key, model in SURVEY_MODELS.items():
        stamps = db.session.execute(select(model.timestamp).where(model.timestamp >= since)).scalars()
        for stamp in stamps:
            entry = by_date.get(to_local(stamp, tz_name).date())
            if entry:
                entry[key] += 1

    for entry in series:
        entry["total"] = entry["employer"] + entry["student"]
    return series

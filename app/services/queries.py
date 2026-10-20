"""Search / filter / sort logic for the admin response lists (and the exports built from them)."""
from datetime import date, timedelta

from sqlalchemy import asc, desc, or_, select

from ..timeutil import local_day_start_utc

SORTS = {
    "newest": ("timestamp", "desc"),
    "oldest": ("timestamp", "asc"),
    "name": (None, "asc"),  # resolved to spec.name_field
}
MAX_SEARCH_LENGTH = 100


def escape_like(term):
    """Make %, _ and \\ in user input match literally inside a LIKE pattern."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parse_date(value):
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def parse_filters(args, spec):
    """Whitelist-clean the query string. Unknown fields/values are dropped, never trusted."""
    cleaned = {}

    term = (args.get("q") or "").strip()[:MAX_SEARCH_LENGTH]
    if term:
        cleaned["q"] = term

    for option in spec.filters:
        value = (args.get(option.name) or "").strip()
        if value in option.choices:
            cleaned[option.name] = value

    for key in ("date_from", "date_to"):
        parsed = _parse_date(args.get(key))
        if parsed:
            cleaned[key] = parsed.isoformat()

    sort = args.get("sort")
    if sort in SORTS and sort != "newest":
        cleaned["sort"] = sort
    return cleaned


def build_query(model, spec, filters, tz_name):
    stmt = select(model)

    term = filters.get("q")
    if term:
        pattern = f"%{escape_like(term)}%"
        stmt = stmt.where(or_(*[getattr(model, name).ilike(pattern, escape="\\") for name in spec.search_fields]))

    for option in spec.filters:
        if option.name in filters:
            stmt = stmt.where(getattr(model, option.name) == filters[option.name])

    if "date_from" in filters:
        start = local_day_start_utc(date.fromisoformat(filters["date_from"]), tz_name)
        stmt = stmt.where(model.timestamp >= start)
    if "date_to" in filters:
        end = local_day_start_utc(date.fromisoformat(filters["date_to"]) + timedelta(days=1), tz_name)
        stmt = stmt.where(model.timestamp < end)

    column_name, direction = SORTS[filters.get("sort", "newest")]
    column = getattr(model, column_name or spec.name_field)
    order = desc if direction == "desc" else asc
    return stmt.order_by(order(column), order(model.id))


def row_average(record, spec):
    """Mean of a response's 1-5 ratings (zeros/NULLs from legacy rows are ignored)."""
    values = [getattr(record, f) for f in spec.rating_fields]
    values = [v for v in values if v]
    return round(sum(values) / len(values), 2) if values else None

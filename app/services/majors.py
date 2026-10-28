"""Results by major (мэргэжил).

No Flask or database imports: every function takes plain record objects (anything with the survey's
attributes) and returns plain dicts/lists, like services/export.py. That keeps it easy to test.

How responses are assigned to a major
* Student survey: one free-text major per response.
* Employer survey: one free-text *list* of majors whose students intern there ("Гагнуур, Автомеханик").
  The employer is counted once under every major it lists. Its 1-5 ratings describe the employer's
  graduates as a whole (the survey does not ask per major), so the same rating is shared by each
  major the employer lists.

Free text is grouped case- and whitespace-insensitively ("Гагнуур", " гагнуур ", "ГАГНУУР" are one
major); the most common spelling is shown. Different wording ("Гагнуур" vs "Гагнуурчин") is
different text and is NOT merged - the data has to be consistent for that.
"""
import re
from collections import Counter

from .answers import answer

_SPLIT_RE = re.compile(r"[,;\n\r]+")


# --------------------------------------------------------------------------------------
# Normalising free text
# --------------------------------------------------------------------------------------
def clean_major(text):
    """Trim and collapse inner whitespace: '  Авто   механик ' -> 'Авто механик'."""
    return " ".join((text or "").split())


def major_key(text):
    """Grouping key. casefold() understands Cyrillic (Ө/ө, Ү/ү), unlike SQLite's lower()."""
    return clean_major(text).casefold()


def split_majors(text):
    """'Гагнуур, гагнуур\\nАвтомеханик' -> ['Гагнуур', 'Автомеханик'] (no duplicates, order kept)."""
    seen = {}
    for part in _SPLIT_RE.split(text or ""):
        name = clean_major(part)
        if name and major_key(name) not in seen:
            seen[major_key(name)] = name
    return list(seen.values())


def majors_of(record, spec):
    """The list of majors a single response belongs to."""
    value = getattr(record, spec.major_field, None)
    if spec.key == "employer":
        return split_majors(value)
    name = clean_major(value)
    return [name] if name else []


# --------------------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------------------
def _average(values):
    values = [v for v in values if v]  # NULL and legacy 0 placeholders are not scores
    return round(sum(values) / len(values), 2) if values else None


def _percent(part, whole):
    return round(part * 100 / whole, 1) if whole else None


def summarize(records, spec):
    """Group `records` of one survey by major.

    Returns {"rows": [...], "unassigned": int, "total": int}. Each row:
        key, label, count, average (mean of the question averages), averages {field: avg},
        highlights [{label, positive, total, percent}]
    Rows are ordered by number of responses (desc), then name.
    """
    buckets = {}      # key -> {"spellings": Counter, "records": [..]}
    unassigned = 0
    records = list(records)

    for record in records:
        names = majors_of(record, spec)
        if not names:
            unassigned += 1
            continue
        for name in names:
            bucket = buckets.setdefault(major_key(name), {"spellings": Counter(), "records": []})
            bucket["spellings"][name] += 1
            bucket["records"].append(record)

    rows = []
    for key, bucket in buckets.items():
        group = bucket["records"]
        averages = {f: _average(answer(r, f) for r in group) for f in spec.rating_fields}
        scored = [v for v in averages.values() if v is not None]

        highlights = []
        for field, label, positive_value in spec.major_highlights:
            answers = [getattr(r, field, None) for r in group]
            answers = [a for a in answers if a not in (None, "")]
            positive = sum(1 for a in answers if a == positive_value)
            highlights.append({"label": label, "positive": positive, "total": len(answers),
                               "percent": _percent(positive, len(answers))})

        rows.append({
            "key": key,
            "label": bucket["spellings"].most_common(1)[0][0],
            "count": len(group),
            "average": round(sum(scored) / len(scored), 2) if scored else None,
            "averages": averages,
            "highlights": highlights,
        })

    rows.sort(key=lambda row: (-row["count"], row["label"].casefold()))
    return {"rows": rows, "unassigned": unassigned, "total": len(records)}


def combine(student, employer):
    """One row per major across both surveys, for the overview table."""
    merged = {}
    for name, result in (("student", student), ("employer", employer)):
        for row in result["rows"]:
            entry = merged.setdefault(row["key"], {
                "key": row["key"], "label": row["label"],
                "student_count": 0, "student_average": None,
                "employer_count": 0, "employer_average": None,
            })
            entry[f"{name}_count"] = row["count"]
            entry[f"{name}_average"] = row["average"]
            if name == "student":
                entry["label"] = row["label"]  # students typed the major themselves: prefer their spelling
    return sorted(merged.values(),
                  key=lambda e: (-(e["student_count"] + e["employer_count"]), e["label"].casefold()))


def export_table(result, spec):
    """(headers, rows) for the CSV / Excel download of one survey's results by major."""
    headers = (
        ["Мэргэжил", "Хариултын тоо", "Дундаж оноо (1-5)"]
        + [f"{q.short} (1-5)" for q in spec.rating_questions]
        + [f"{label} (%)" for _, label, _ in spec.major_highlights]
    )
    rows = []
    for row in result["rows"]:
        rows.append(
            [row["label"], row["count"], row["average"]]
            + [row["averages"].get(q.field) for q in spec.rating_questions]
            + [h["percent"] for h in row["highlights"]]
        )
    return headers, rows

"""Admin-editable survey questions: the rules, with no Flask or database imports.

`app/questions.py` holds the DEFAULT questions. An admin's edits are kept as one small JSON document
per survey (table `survey_configs`) and layered on top of those defaults:

    {
      "title":   "<survey title>"                      # omitted/None = default title
      "groups":  [ {"key", "title", "hint", "active",  # omitted = the default rating groups
                    "questions": [ {"field", "label", "short", "active"} ... ]} ... ],
      "labels":  {"company_name": "<question text>"},  # wording of the fixed questions
      "choices": {"aimag_city": ["A", "B"]},           # answer choices of the dropdown questions
    }

Everything here takes and returns plain dicts, so it is easy to test. Edit functions never modify
the document they are given; they return a new one, or raise `ConfigError` whose message (in
Mongolian) is shown to the admin as is.

Hiding a question never deletes data: the answers stay in the database and come back when the
question is shown again.
"""
import secrets
from dataclasses import dataclass, replace
from typing import Optional, Tuple

from ..questions import FilterOption, Question, RatingGroup

MAX_TITLE = 200
MAX_GROUP_TITLE = 200
MAX_HINT = 200
MAX_LABEL = 300
MAX_SHORT = 80
MAX_GROUPS = 12
MAX_QUESTIONS = 60          # rating questions per survey, hidden ones included
MAX_CHOICES = 50
MAX_CHOICE_LENGTH = 100

DIRECTIONS = ("up", "down")


class ConfigError(ValueError):
    """An edit that was rejected. The message is meant for the admin and is already translated."""


@dataclass(frozen=True)
class InfoField:
    """A fixed (non-rating) question of a survey form: only its wording and choices are editable."""

    name: str                              # form field / model column name
    label: str                             # default question text
    choices: Optional[Tuple[str, ...]]     # default answer choices; None when it is not a dropdown
    max_len: Optional[int] = None          # longest answer the database column can hold


# --------------------------------------------------------------------------------------
# Cleaning
# --------------------------------------------------------------------------------------
def _squash(value):
    """Collapse all whitespace (including line breaks) to single spaces; non-strings become ''."""
    return " ".join(value.split()) if isinstance(value, str) else ""


def _required(value, name, limit):
    text = _squash(value)
    if not text:
        raise ConfigError(f"{name} хоосон байж болохгүй.")
    if len(text) > limit:
        raise ConfigError(f"{name}: хамгийн ихдээ {limit} тэмдэгт оруулна уу.")
    return text


def _optional(value, name, limit):
    text = _squash(value)
    if len(text) > limit:
        raise ConfigError(f"{name}: хамгийн ихдээ {limit} тэмдэгт оруулна уу.")
    return text


def _auto_short(label):
    """Table/export header for a question that was given none: the question text, shortened."""
    return label if len(label) <= MAX_SHORT else label[: MAX_SHORT - 1].rstrip() + "…"


def _unique_strings(values):
    seen, result = set(), []
    for value in values if isinstance(values, (list, tuple)) else ():
        text = _squash(value)[:MAX_CHOICE_LENGTH]
        if text and text.casefold() not in seen:
            seen.add(text.casefold())
            result.append(text)
    return result


# --------------------------------------------------------------------------------------
# Document <-> defaults
# --------------------------------------------------------------------------------------
def default_groups(spec):
    """The rating groups of `spec` (the defaults in questions.py) in document form."""
    return [
        {
            "key": group.key,
            "title": group.title,
            "hint": group.hint,
            "active": True,
            "questions": [
                {"field": q.field, "label": q.label, "short": q.short, "active": True}
                for q in group.questions
            ],
        }
        for group in spec.rating_groups
    ]


def _clean_groups(raw_groups):
    groups, group_keys, fields = [], set(), set()
    for raw in raw_groups:
        if not isinstance(raw, dict):
            continue
        key = raw.get("key")
        title = _squash(raw.get("title"))[:MAX_GROUP_TITLE]
        if not isinstance(key, str) or not key or key in group_keys or not title:
            continue
        group_keys.add(key)

        questions = []
        for item in raw.get("questions") if isinstance(raw.get("questions"), list) else ():
            if not isinstance(item, dict):
                continue
            field = item.get("field")
            label = _squash(item.get("label"))[:MAX_LABEL]
            if not isinstance(field, str) or not field or field in fields or not label:
                continue
            fields.add(field)
            questions.append({
                "field": field,
                "label": label,
                "short": _squash(item.get("short"))[:MAX_SHORT] or _auto_short(label),
                "active": item.get("active") is not False,
            })
        groups.append({
            "key": key,
            "title": title,
            "hint": _squash(raw.get("hint"))[:MAX_HINT],
            "active": raw.get("active") is not False,
            "questions": questions,
        })
    return groups


def normalize(raw):
    """A complete, well-formed copy of a stored document. Garbage is dropped, never trusted."""
    raw = raw if isinstance(raw, dict) else {}
    doc = {"title": _squash(raw.get("title"))[:MAX_TITLE] or None, "labels": {}, "choices": {}}

    labels = raw.get("labels")
    for name, value in (labels.items() if isinstance(labels, dict) else ()):
        text = _squash(value)[:MAX_LABEL]
        if isinstance(name, str) and name and text:
            doc["labels"][name] = text

    choices = raw.get("choices")
    for name, values in (choices.items() if isinstance(choices, dict) else ()):
        cleaned = _unique_strings(values)
        if isinstance(name, str) and name and cleaned:
            doc["choices"][name] = cleaned

    if isinstance(raw.get("groups"), list):
        doc["groups"] = _clean_groups(raw["groups"])
    return doc


def _groups(doc, spec):
    """The editable list of groups; the defaults are copied in the first time a group is edited."""
    if doc.get("groups") is None:
        doc["groups"] = default_groups(spec)
    return doc["groups"]


# --------------------------------------------------------------------------------------
# Resolving: defaults + document -> the SurveySpec the rest of the app uses
# --------------------------------------------------------------------------------------
def _with_old_choices(new, old):
    """New choices first, then any default not in them, so responses saved earlier stay filterable."""
    merged = list(new)
    known = {value.casefold() for value in merged}
    merged.extend(value for value in old if value.casefold() not in known)
    return tuple(merged)


def resolve(spec, raw_doc):
    """`spec` (the defaults) with the admin's edits applied. No edits -> `spec` itself."""
    if not raw_doc:
        return spec
    doc = normalize(raw_doc)

    rating_groups = spec.rating_groups
    if doc.get("groups") is not None:
        built = []
        for group in doc["groups"]:
            questions = tuple(Question(q["field"], q["label"], q["short"]) for q in group["questions"] if q["active"])
            if group["active"] and questions:   # a hidden or empty group is not shown at all
                built.append(RatingGroup(group["key"], group["title"], questions, group["hint"]))
        rating_groups = tuple(built)

    filters = tuple(
        FilterOption(f.name, f.label, _with_old_choices(doc["choices"][f.name], f.choices))
        if f.name in doc["choices"] else f
        for f in spec.filters
    )
    return replace(
        spec,
        title=doc["title"] or spec.title,
        rating_groups=rating_groups,
        filters=filters,
        field_labels=tuple(doc["labels"].items()),
        choice_overrides=tuple((name, tuple(values)) for name, values in doc["choices"].items()),
    )


# --------------------------------------------------------------------------------------
# Finding things
# --------------------------------------------------------------------------------------
def _find_group(groups, key):
    for group in groups:
        if group["key"] == key:
            return group
    raise ConfigError("Бүлэг олдсонгүй. Хуудсаа дахин ачаална уу.")


def _find_question(groups, field):
    for group in groups:
        for question in group["questions"]:
            if question["field"] == field:
                return group, question
    raise ConfigError("Асуулт олдсонгүй. Хуудсаа дахин ачаална уу.")


def _new_key(prefix, taken, nbytes):
    while True:
        key = prefix + secrets.token_hex(nbytes)
        if key not in taken:
            return key


def _check_direction(direction):
    if direction not in DIRECTIONS:
        raise ConfigError("Чиглэл буруу байна.")


def _swap(items, index, direction):
    """Move items[index] one step; at either end nothing happens."""
    other = index - 1 if direction == "up" else index + 1
    if 0 <= other < len(items):
        items[index], items[other] = items[other], items[index]


# --------------------------------------------------------------------------------------
# Edits. Each returns a new document (the `add_*` ones also return the new key).
# --------------------------------------------------------------------------------------
def set_title(doc, spec, title):
    doc = normalize(doc)
    text = _required(title, "Гарчиг", MAX_TITLE)
    doc["title"] = None if text == spec.title else text
    return doc


def add_group(doc, spec, title, hint=""):
    doc = normalize(doc)
    groups = _groups(doc, spec)
    if len(groups) >= MAX_GROUPS:
        raise ConfigError(f"Хамгийн ихдээ {MAX_GROUPS} бүлэг байж болно.")
    key = _new_key("g_", {g["key"] for g in groups}, 3)
    groups.append({
        "key": key,
        "title": _required(title, "Бүлгийн гарчиг", MAX_GROUP_TITLE),
        "hint": _optional(hint, "Үнэлгээний тайлбар", MAX_HINT),
        "active": True,
        "questions": [],
    })
    return doc, key


def update_group(doc, spec, key, title, hint=""):
    doc = normalize(doc)
    group = _find_group(_groups(doc, spec), key)
    group["title"] = _required(title, "Бүлгийн гарчиг", MAX_GROUP_TITLE)
    group["hint"] = _optional(hint, "Үнэлгээний тайлбар", MAX_HINT)
    return doc


def move_group(doc, spec, key, direction):
    _check_direction(direction)
    doc = normalize(doc)
    groups = _groups(doc, spec)
    _swap(groups, groups.index(_find_group(groups, key)), direction)
    return doc


def toggle_group(doc, spec, key):
    """Show/hide a whole group. Returns (document, group is now visible)."""
    doc = normalize(doc)
    group = _find_group(_groups(doc, spec), key)
    group["active"] = not group["active"]
    return doc, group["active"]


def add_question(doc, spec, group_key, label, short=""):
    doc = normalize(doc)
    groups = _groups(doc, spec)
    group = _find_group(groups, group_key)
    label = _required(label, "Асуултын текст", MAX_LABEL)
    short = _optional(short, "Товч нэр", MAX_SHORT) or _auto_short(label)
    if sum(len(g["questions"]) for g in groups) >= MAX_QUESTIONS:
        raise ConfigError(f"Нэг судалгаанд хамгийн ихдээ {MAX_QUESTIONS} үнэлгээний асуулт байж болно.")
    field = _new_key("x_", {q["field"] for g in groups for q in g["questions"]}, 4)
    group["questions"].append({"field": field, "label": label, "short": short, "active": True})
    return doc, field


def update_question(doc, spec, field, label, short=""):
    doc = normalize(doc)
    _, question = _find_question(_groups(doc, spec), field)
    question["label"] = _required(label, "Асуултын текст", MAX_LABEL)
    question["short"] = _optional(short, "Товч нэр", MAX_SHORT) or _auto_short(question["label"])
    return doc


def move_question(doc, spec, field, direction):
    """Move a question up/down inside its group."""
    _check_direction(direction)
    doc = normalize(doc)
    group, question = _find_question(_groups(doc, spec), field)
    _swap(group["questions"], group["questions"].index(question), direction)
    return doc


def toggle_question(doc, spec, field):
    """Show/hide a question. Returns (document, question is now visible)."""
    doc = normalize(doc)
    _, question = _find_question(_groups(doc, spec), field)
    question["active"] = not question["active"]
    return doc, question["active"]


def protected_choices(spec, name):
    """Answers the results-by-major page counts as 'positive' for `name`; they must stay choosable."""
    return tuple(positive for field, _label, positive in spec.major_highlights if field == name)


def parse_choices(text, max_len=None):
    """One answer choice per line -> cleaned list. `max_len` is the database column's limit."""
    values = [v for v in (_squash(line) for line in (text or "").splitlines()) if v]
    if not 1 <= len(values) <= MAX_CHOICES:
        raise ConfigError(f"Хариултын сонголт хамгийн багадаа 1, хамгийн ихдээ {MAX_CHOICES} байх ёстой.")
    limit = min(MAX_CHOICE_LENGTH, max_len) if max_len else MAX_CHOICE_LENGTH
    seen = set()
    for value in values:
        if len(value) > limit:
            raise ConfigError(f"«{value}» сонголт хэт урт байна (хамгийн ихдээ {limit} тэмдэгт).")
        if value.casefold() in seen:
            raise ConfigError(f"«{value}» сонголт давхардсан байна.")
        seen.add(value.casefold())
    return values


def update_info_field(doc, spec, info, name, label, choices_text=""):
    """Reword a fixed question and, for a dropdown, change its answer choices.

    A value equal to the default is not stored, so later changes to questions.py still show up.
    """
    field = info.get(name)
    if field is None:
        raise ConfigError("Энэ асуултыг засах боломжгүй.")
    doc = normalize(doc)

    text = _required(label, "Асуултын текст", MAX_LABEL)
    if text == field.label:
        doc["labels"].pop(name, None)
    else:
        doc["labels"][name] = text

    if field.choices is not None:
        values = parse_choices(choices_text, field.max_len)
        for needed in protected_choices(spec, name):
            if needed not in values:
                raise ConfigError(f"«{needed}» сонголтыг устгах боломжгүй: үр дүнгийн тооцоонд ашиглагддаг.")
        if tuple(values) == tuple(field.choices):
            doc["choices"].pop(name, None)
        else:
            doc["choices"][name] = values
    return doc


# --------------------------------------------------------------------------------------
# One entry point for the admin form
# --------------------------------------------------------------------------------------
def apply_action(doc, spec, info, action, form):
    """Run the editor action named `action` with the values in `form` (anything with `.get`).

    Returns (new document, success message, page anchor to scroll back to).
    """
    def get(name):
        value = form.get(name)
        return value if isinstance(value, str) else ""

    key = get("key")
    if action == "title":
        return set_title(doc, spec, get("title")), "Гарчиг хадгалагдлаа.", "title"
    if action == "add_group":
        new_doc, new_key = add_group(doc, spec, get("title"), get("hint"))
        return new_doc, "Бүлэг нэмэгдлээ.", f"g-{new_key}"
    if action == "update_group":
        return update_group(doc, spec, key, get("title"), get("hint")), "Бүлэг хадгалагдлаа.", f"g-{key}"
    if action == "move_group":
        return move_group(doc, spec, key, get("direction")), "Эрэмбэ өөрчлөгдлөө.", f"g-{key}"
    if action == "toggle_group":
        new_doc, visible = toggle_group(doc, spec, key)
        return new_doc, ("Бүлгийг дахин харуулж байна." if visible else "Бүлгийг нууллаа."), f"g-{key}"
    if action == "add_question":
        new_doc, field = add_question(doc, spec, key, get("label"), get("short"))
        return new_doc, "Асуулт нэмэгдлээ.", f"q-{field}"
    if action == "update_question":
        return update_question(doc, spec, key, get("label"), get("short")), "Асуулт хадгалагдлаа.", f"q-{key}"
    if action == "move_question":
        return move_question(doc, spec, key, get("direction")), "Эрэмбэ өөрчлөгдлөө.", f"q-{key}"
    if action == "toggle_question":
        new_doc, visible = toggle_question(doc, spec, key)
        return new_doc, ("Асуултыг дахин харуулж байна." if visible else "Асуултыг нууллаа."), f"q-{key}"
    if action == "update_field":
        new_doc = update_info_field(doc, spec, info, key, get("label"), get("choices"))
        return new_doc, "Асуулт хадгалагдлаа.", f"f-{key}"
    raise ConfigError("Үйлдэл танигдсангүй.")


# --------------------------------------------------------------------------------------
# What the editor page shows
# --------------------------------------------------------------------------------------
def describe(spec, raw_doc, info):
    """Everything the editor template needs, including hidden questions and unchanged defaults."""
    doc = normalize(raw_doc)
    groups = doc["groups"] if doc.get("groups") is not None else default_groups(spec)

    view_groups = []
    for g_index, group in enumerate(groups):
        questions = group["questions"]
        view_groups.append({
            **group,
            "number": g_index + 1,
            "first": g_index == 0,
            "last": g_index == len(groups) - 1,
            "questions": [
                {**q, "first": i == 0, "last": i == len(questions) - 1}
                for i, q in enumerate(questions)
            ],
        })

    fields = []
    for name, field in info.items():
        current_choices = doc["choices"].get(name)
        fields.append({
            "name": name,
            "label": doc["labels"].get(name, field.label),
            "default_label": field.label,
            "changed": name in doc["labels"] or name in doc["choices"],
            "has_choices": field.choices is not None,
            "choices": list(current_choices or field.choices or ()),
            "protected": protected_choices(spec, name),
            "max_len": field.max_len,
        })

    return {
        "title": doc["title"] or spec.title,
        "default_title": spec.title,
        "groups": view_groups,
        "fields": fields,
        "question_count": sum(len(g["questions"]) for g in groups),
    }

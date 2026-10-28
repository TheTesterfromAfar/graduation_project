"""Read one answer from a saved response. No Flask or database imports.

Original questions are real columns on the response table (`q2_1_1`, `env_3`, ...). Questions an
admin adds from the web have no column; their answers live in the JSON column `extra_answers`.
Everything that reads ratings (dashboard, lists, by-major, exports) goes through `answer()`, so it
does not need to know which kind a question is.
"""


def answer(record, field):
    """The value of `field` for `record`, or None when the respondent was not asked / did not answer."""
    value = getattr(record, field, None)
    if value is not None:
        return value
    extra = getattr(record, "extra_answers", None)
    return extra.get(field) if isinstance(extra, dict) else None

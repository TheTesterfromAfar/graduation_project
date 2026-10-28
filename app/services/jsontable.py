"""Turn the JSON an admin uploaded or pasted into spreadsheet sheets. No Flask or database imports.

`to_sheets(data)` accepts whatever `json.loads` returned and always gives at least one `Sheet`:

* list of objects  [{"Д/Д": 1, "Овог": "Бат"}, ...]  -> one row per object, one column per key
* list of lists    [["Д/Д", "Овог"], [1, "Бат"]]      -> a plain grid, columns named A, B, C ...
* list of values   [1, 2, 3]                          -> a single column
* object of tables {"Sheet1": [...], "Sheet2": [...]} -> one sheet per key (anything else in the
                                                         object goes to an extra "Бусад" sheet)
* object of columns {"Нэр": ["a", "b"], "Нас": [1, 2]} -> one column per key
* any other object                                    -> a two-column Түлхүүр / Утга table
* a bare value                                        -> a single cell

A value that is itself an object or list is shown as compact JSON text inside its cell.
"""
import json
import math
from dataclasses import dataclass, field
from typing import List

MAX_COLUMNS = 200            # a safety net against pathological data, not a limit people will meet
VALUE_COLUMN = "Утга"
KEY_COLUMN = "Түлхүүр"
OTHER_SHEET = "Бусад"
DEFAULT_SHEET = "Хүснэгт"


@dataclass
class Sheet:
    name: str
    columns: List[str]
    rows: List[list] = field(default_factory=list)   # each row has exactly len(columns) cells
    columns_cut: bool = False                        # True when MAX_COLUMNS dropped some columns


# --------------------------------------------------------------------------------------
# Cells
# --------------------------------------------------------------------------------------
def cell(value):
    """A JSON value as something a spreadsheet cell can hold: text, number, bool or None."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (int, float)):
        return str(value) if isinstance(value, float) and not math.isfinite(value) else value
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))   # nested object / list


def column_letters(index):
    """0 -> 'A', 25 -> 'Z', 26 -> 'AA' (spreadsheet column names)."""
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _is_scalar(value):
    return not isinstance(value, (dict, list))


# --------------------------------------------------------------------------------------
# Tables
# --------------------------------------------------------------------------------------
def _cap(sheet):
    if len(sheet.columns) > MAX_COLUMNS:
        sheet.columns = sheet.columns[:MAX_COLUMNS]
        sheet.rows = [row[:MAX_COLUMNS] for row in sheet.rows]
        sheet.columns_cut = True
    return sheet


def _from_objects(name, items):
    columns = []
    seen = set()
    for item in items:
        for key in item:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    rows = [[cell(item.get(key)) for key in columns] for item in items]
    return _cap(Sheet(name, columns, rows))


def _from_grid(name, items):
    width = max((len(item) for item in items), default=0)
    columns = [column_letters(i) for i in range(width)]
    rows = [[cell(item[i]) if i < len(item) else None for i in range(width)] for item in items]
    return _cap(Sheet(name, columns, rows))


def _from_list(name, items):
    if all(isinstance(item, dict) for item in items) and items:
        return _from_objects(name, items)
    if all(isinstance(item, list) for item in items) and items:
        return _from_grid(name, items)
    return Sheet(name, [VALUE_COLUMN], [[cell(item)] for item in items])


def _from_columns(name, mapping):
    columns = list(mapping)
    height = max((len(values) for values in mapping.values()), default=0)
    rows = [[cell(mapping[key][i]) if i < len(mapping[key]) else None for key in columns] for i in range(height)]
    return _cap(Sheet(name, columns, rows))


def _key_values(name, mapping):
    return Sheet(name, [KEY_COLUMN, VALUE_COLUMN], [[key, cell(value)] for key, value in mapping.items()])


def _is_table(value):
    """A non-empty list of objects or of lists: something that is a table in its own right."""
    return (isinstance(value, list) and value
            and (all(isinstance(v, dict) for v in value) or all(isinstance(v, list) for v in value)))


def to_sheets(data, default_name=DEFAULT_SHEET):
    """Every JSON document becomes one or more sheets (never an empty list)."""
    if isinstance(data, list):
        return [_from_list(default_name, data)]

    if isinstance(data, dict):
        if not data:
            return [Sheet(default_name, [KEY_COLUMN, VALUE_COLUMN])]
        if all(isinstance(v, list) and all(_is_scalar(x) for x in v) for v in data.values()):
            return [_from_columns(default_name, data)]           # {"col": [values...], ...}

        tables = {key: value for key, value in data.items() if _is_table(value)}
        if tables:
            sheets = [_from_list(str(key), value) for key, value in tables.items()]
            rest = {key: value for key, value in data.items() if key not in tables}
            if rest:
                sheets.append(_key_values(OTHER_SHEET, rest))
            return sheets
        return [_key_values(default_name, data)]

    return [Sheet(default_name, [VALUE_COLUMN], [[cell(data)]])]


def parse(text):
    """JSON text -> sheets. Raises ValueError if the text is not (or is too deeply nested to be) JSON."""
    try:
        return to_sheets(json.loads(text))
    except RecursionError as exc:
        raise ValueError("JSON хэт гүн давхарласан байна.") from exc

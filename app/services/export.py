"""CSV / Excel export. No Flask or database imports: takes plain rows, returns bytes/text chunks."""
import csv
import io
import re
from datetime import datetime

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font

from ..timeutil import format_local
from .answers import answer

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CSV_MIME = "text/csv; charset=utf-8"

# A leading + or - is only dangerous if what follows can be parsed as a formula. Phone numbers such
# as "+976 99112233" or "-5" are made of digits, spaces, dots, hyphens and brackets only - leave them.
_PLAIN_SIGNED_NUMBER = re.compile(r"^[+-][0-9][0-9 ()\-.]*$")


def neutralize(value):
    """Defuse spreadsheet formula injection (CWE-1236).

    Free-text answers that start with =, @, +, - (or tab/CR) are executed as formulas when the file is
    opened in Excel/LibreOffice. Prefixing a single quote makes the application treat them as text.
    """
    if not isinstance(value, str) or not value:
        return value
    if value[0] in "\t\r":
        return "'" + value
    stripped = value.lstrip(" ")
    head = stripped[:1]
    if head in ("=", "@"):
        return "'" + value
    if head in ("+", "-") and not _PLAIN_SIGNED_NUMBER.match(stripped):
        return "'" + value
    return value


def format_cell(value, tz_name):
    if isinstance(value, datetime):
        return format_local(value, tz_name)
    if value is None:
        return ""
    return value


def table_rows(records, columns, tz_name):
    """Yield one list of cell values per record, following `columns` = [(attribute, header), ...]."""
    for record in records:
        yield [format_cell(answer(record, attr), tz_name) for attr, _ in columns]


def iter_csv(headers, rows):
    """Yield CSV text chunks. Starts with a UTF-8 BOM so Excel shows Cyrillic correctly."""
    yield "\ufeff"
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    def drain():
        data = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return data

    writer.writerow([neutralize(header) for header in headers])
    yield drain()
    for row in rows:
        writer.writerow([neutralize(cell) for cell in row])
        yield drain()


def build_xlsx(headers, rows, sheet_title="Хариултууд"):
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(title=sheet_title)
    sheet.freeze_panes = "A2"

    header_cells = []
    for header in headers:
        cell = WriteOnlyCell(sheet, value=neutralize(header))
        cell.font = Font(bold=True)
        header_cells.append(cell)
    sheet.append(header_cells)

    for row in rows:
        sheet.append([neutralize(cell) for cell in row])

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


# --------------------------------------------------------------------------------------
# Workbook with several sheets (the admin's JSON data shown as a spreadsheet)
# --------------------------------------------------------------------------------------
EXCEL_MAX_CELL = 32767                     # Excel's limit on the text in one cell
_SHEET_NAME_BAD = re.compile(r"[\[\]:*?/\\]")


def _excel_cell(value):
    """Safe to hand to openpyxl: no control characters (openpyxl raises on them), no formulas."""
    if isinstance(value, str):
        return neutralize(ILLEGAL_CHARACTERS_RE.sub("", value))[:EXCEL_MAX_CELL]
    return value


def sheet_titles(names):
    """Excel-legal, unique worksheet names (max 31 characters, none of []:*?/\\, not empty)."""
    used, titles = set(), []
    for name in names:
        base = _SHEET_NAME_BAD.sub("_", ILLEGAL_CHARACTERS_RE.sub("", str(name))).strip("' ")[:31] or "Sheet"
        title, n = base, 2
        while title.casefold() in used:
            suffix = f" ({n})"
            title, n = base[: 31 - len(suffix)] + suffix, n + 1
        used.add(title.casefold())
        titles.append(title)
    return titles


def build_workbook(sheets):
    """`sheets` = [(name, headers, rows), ...] -> an .xlsx file (BytesIO) with one worksheet each."""
    workbook = Workbook(write_only=True)
    for title, (_, headers, rows) in zip(sheet_titles([name for name, _, _ in sheets]), sheets):
        sheet = workbook.create_sheet(title=title)
        sheet.freeze_panes = "A2"
        header_cells = []
        for header in headers:
            header_cell = WriteOnlyCell(sheet, value=_excel_cell(header))
            header_cell.font = Font(bold=True)
            header_cells.append(header_cell)
        sheet.append(header_cells)
        for row in rows:
            sheet.append([_excel_cell(cell) for cell in row])

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output

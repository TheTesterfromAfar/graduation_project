"""CSV / Excel export. No Flask or database imports: takes plain rows, returns bytes/text chunks."""
import csv
import io
import re
from datetime import datetime

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
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

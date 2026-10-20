import io

import openpyxl

from app.services.export import build_xlsx, iter_csv, neutralize


def test_neutralize_blocks_formula_prefixes():
    for risky in ("=1+1", "@SUM(A1)", "+cmd|' /C calc'!A0", "-2+3+cmd", "\t=1", "  =1+1"):
        assert neutralize(risky).startswith("'"), risky


def test_neutralize_keeps_normal_values():
    for safe in ("Өвөрхангай", "+97699112233", "+976 9911-2233", "-5", "(976) 99112233", "", None, 42):
        assert neutralize(safe) == safe


def test_csv_starts_with_bom_and_quotes_commas():
    text = "".join(iter_csv(["a", "b"], [["x,y", "өгөгдөл"]]))
    assert text.startswith("\ufeff")
    assert '"x,y"' in text and "өгөгдөл" in text


def test_xlsx_roundtrip():
    buffer = build_xlsx(["Нэр", "Оноо"], [["Бат", 5], ["=EVIL()", 3]])
    sheet = openpyxl.load_workbook(io.BytesIO(buffer.read())).active
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0] == ("Нэр", "Оноо") and rows[1] == ("Бат", 5)
    assert rows[2][0] == "'=EVIL()"

import csv
import io
from datetime import datetime

import openpyxl

from app.models import AdminDataEntry, EmployerSurvey, StudentSurvey

from .conftest import add, attribute, count, first_id


def add_employer(app, company, **kwargs):
    defaults = dict(respondent_name="Бат", position="Захирал", phone="99112233", email="a@b.mn",
                    aimag_city="Өвөрхангай", q2_1_1=4, q2_1_2=2)
    defaults.update(kwargs)
    add(app, EmployerSurvey(company_name=company, **defaults))


def test_dashboard_with_and_without_data(app, admin_client):
    assert admin_client.get("/admin/").status_code == 200
    add_employer(app, "Өвөр ХХК")
    add(app, StudentSurvey(major="Гагнуур", company_name="X", env_1=5, soft_1=0))
    page = admin_client.get("/admin/").get_data(as_text=True)
    assert "Дундаж" in page


def test_search_is_case_insensitive_for_cyrillic(app, admin_client):
    add_employer(app, "Өвөрхангай Барилга ХХК")
    add_employer(app, "Улаанбаатар Метал ХХК", aimag_city="Улаанбаатар")
    page = admin_client.get("/admin/responses/employer?q=өвөрхангай").get_data(as_text=True)
    assert "Өвөрхангай Барилга ХХК" in page and "Улаанбаатар Метал" not in page


def test_like_wildcards_in_search_are_literal(app, admin_client):
    add_employer(app, "Alpha")
    page = admin_client.get("/admin/responses/employer?q=%25").get_data(as_text=True)
    assert "Alpha" not in page


def test_filters_dates_and_unknown_values(app, admin_client):
    add_employer(app, "Old", timestamp=datetime(2026, 1, 5, 10, 0))
    add_employer(app, "New", timestamp=datetime(2026, 3, 5, 10, 0), aimag_city="Төв")
    url = "/admin/responses/employer"
    assert "Old" not in admin_client.get(f"{url}?date_from=2026-02-01").get_data(as_text=True)
    assert "New" not in admin_client.get(f"{url}?date_to=2026-02-01").get_data(as_text=True)
    assert "Old" not in admin_client.get(f"{url}?aimag_city=Төв").get_data(as_text=True)
    # junk values are ignored rather than crashing or filtering everything out
    page = admin_client.get(f"{url}?aimag_city=DROP&date_from=garbage&sort=evil&page=zzz").get_data(as_text=True)
    assert "Old" in page and "New" in page


def test_pagination(app, admin_client):
    for i in range(45):
        add_employer(app, f"Company {i:02d}")
    first = admin_client.get("/admin/responses/employer").get_data(as_text=True)
    assert "Хуудас 1 / 3" in first
    assert admin_client.get("/admin/responses/employer?page=99").status_code == 200


def test_unknown_survey_type_is_404(admin_client):
    assert admin_client.get("/admin/responses/nope").status_code == 404
    assert admin_client.get("/admin/export/nope/csv").status_code == 404
    assert admin_client.get("/admin/export/employer/exe").status_code == 404


def test_csv_export_is_excel_friendly_and_formula_safe(app, admin_client):
    add_employer(app, "=HYPERLINK(\"http://evil\")", respondent_name="@SUM(A1)", phone="+97699112233")
    response = admin_client.get("/admin/export/employer/csv")
    assert response.mimetype == "text/csv"
    assert response.data.startswith(b"\xef\xbb\xbf")              # UTF-8 BOM for Excel
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert rows[0][0] == "Огноо" and "Байгууллагын нэр" in rows[0]
    record = dict(zip(rows[0], rows[1]))
    assert record["Байгууллагын нэр"].startswith("'=")
    assert record["Нэр"].startswith("'@")
    assert record["Утас"] == "+97699112233"                        # real phone numbers untouched


def test_excel_export_respects_filters(app, admin_client):
    add_employer(app, "Keep ХХК", aimag_city="Төв")
    add_employer(app, "Drop ХХК", aimag_city="Булган")
    response = admin_client.get("/admin/export/employer/xlsx?aimag_city=Төв")
    sheet = openpyxl.load_workbook(io.BytesIO(response.data)).active
    values = [row[1] for row in sheet.iter_rows(min_row=2, values_only=True)]
    assert values == ["Keep ХХК"]


def test_json_data_lifecycle(app, admin_client):
    assert admin_client.post("/admin/data/add", data={"text_content": "{not json"}).status_code == 200
    assert count(app, AdminDataEntry) == 0

    assert admin_client.post("/admin/data/add", data={"text_content": '[{"a": 1}]'}).status_code == 302
    entry_id = first_id(app, AdminDataEntry)

    upload = {"json_file": (io.BytesIO('\ufeff{"x": "өгөгдөл"}'.encode("utf-8")), "roster.json")}
    assert admin_client.post("/admin/data/add", data=upload, content_type="multipart/form-data").status_code == 302
    assert count(app, AdminDataEntry) == 2

    assert admin_client.post(f"/admin/data/{entry_id}/edit", data={"content": "oops"}).status_code == 200
    assert admin_client.post(f"/admin/data/{entry_id}/edit", data={"content": '{"b": 2}'}).status_code == 302
    assert attribute(app, AdminDataEntry, entry_id, "content") == '{"b": 2}'

    assert admin_client.post(f"/admin/data/{entry_id}/delete").status_code == 302
    assert count(app, AdminDataEntry) == 1


def test_non_json_upload_is_rejected(app, admin_client):
    upload = {"json_file": (io.BytesIO(b"hello"), "notes.txt")}
    admin_client.post("/admin/data/add", data=upload, content_type="multipart/form-data")
    assert count(app, AdminDataEntry) == 0

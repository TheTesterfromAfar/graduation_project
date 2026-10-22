"""Results by major (мэргэжил): grouping rules, the admin page, the list filter and the exports."""
import csv
import io
from types import SimpleNamespace

import openpyxl

from app.models import EmployerSurvey, StudentSurvey
from app.questions import EMPLOYER, STUDENT
from app.services import majors

from .conftest import add


# ---- pure grouping logic -----------------------------------------------------------------
def test_split_majors_handles_separators_case_and_duplicates():
    assert majors.split_majors("Гагнуур, гагнуур;  Авто   механик\nӨрмөл ,") == ["Гагнуур", "Авто механик", "Өрмөл"]
    assert majors.split_majors("") == [] and majors.split_majors(None) == []


def test_major_key_is_cyrillic_case_insensitive():
    assert majors.major_key("  ӨРМӨЛ ") == majors.major_key("өрмөл")


def _student(major, **kwargs):
    return SimpleNamespace(major=major, **kwargs)


def test_summarize_students_groups_spellings_and_computes_numbers():
    records = [
        _student("Гагнуур", env_1=5, env_2=0, recommend_company="Тийм", received_salary="Үгүй"),
        _student(" гагнуур ", env_1=3, env_2=None, recommend_company="Үгүй", received_salary="Үгүй"),
        _student("Гагнуур", env_1=4, env_2=None, recommend_company="Тийм", received_salary=None),
        _student("Автомеханик", env_1=2),
        _student("   "),
    ]
    result = majors.summarize(records, STUDENT)
    assert result["total"] == 5 and result["unassigned"] == 1
    welding, auto = result["rows"]                      # most responses first
    assert (welding["label"], welding["count"]) == ("Гагнуур", 2 + 1)
    assert welding["averages"]["env_1"] == 4.0
    assert welding["averages"]["env_2"] is None          # 0 and NULL are not scores
    assert welding["average"] == 4.0
    recommend = welding["highlights"][0]
    assert (recommend["positive"], recommend["total"], recommend["percent"]) == (2, 3, 66.7)
    salary = welding["highlights"][1]
    assert (salary["positive"], salary["total"]) == (0, 2)   # a missing answer is not counted
    assert auto["label"] == "Автомеханик" and auto["average"] == 2.0


def test_summarize_employers_counts_an_employer_under_each_major():
    base = {f: None for f in EMPLOYER.rating_fields}
    records = [
        SimpleNamespace(**{**base, "intern_majors": "Гагнуур, Автомеханик", "q2_1_1": 4, "rehire_interest": "Тийм"}),
        SimpleNamespace(**{**base, "intern_majors": "гагнуур", "q2_1_1": 2, "rehire_interest": "Үгүй"}),
        SimpleNamespace(**{**base, "intern_majors": None, "q2_1_1": 5, "rehire_interest": "Тийм"}),  # legacy row
    ]
    result = majors.summarize(records, EMPLOYER)
    by_key = {row["key"]: row for row in result["rows"]}
    assert result["unassigned"] == 1
    assert by_key["гагнуур"]["count"] == 2 and by_key["гагнуур"]["averages"]["q2_1_1"] == 3.0
    assert by_key["автомеханик"]["count"] == 1
    assert by_key["гагнуур"]["highlights"][0]["percent"] == 50.0


def test_combine_and_export_table():
    student = {"rows": [{"key": "гагнуур", "label": "Гагнуур", "count": 3, "average": 4.0, "averages": {}, "highlights": []}]}
    employer = {"rows": [
        {"key": "гагнуур", "label": "гагнуур", "count": 2, "average": 3.0, "averages": {}, "highlights": []},
        {"key": "өрмөл", "label": "Өрмөл", "count": 1, "average": None, "averages": {}, "highlights": []},
    ]}
    merged = majors.combine(student, employer)
    assert [m["label"] for m in merged] == ["Гагнуур", "Өрмөл"]       # the students' spelling wins
    assert merged[0]["student_count"] == 3 and merged[0]["employer_count"] == 2

    result = majors.summarize([_student("Гагнуур", env_1=5, recommend_company="Тийм")], STUDENT)
    headers, rows = majors.export_table(result, STUDENT)
    assert headers[:3] == ["Мэргэжил", "Хариултын тоо", "Дундаж оноо (1-5)"]
    assert len(rows[0]) == len(headers) and rows[0][:3] == ["Гагнуур", 1, 5.0]


# ---- admin page, filter, export -----------------------------------------------------------
def _seed(app):
    add(
        app,
        StudentSurvey(major="Гагнуур", company_name="Эрдэнэ ХХК", env_1=5, recommend_company="Тийм"),
        StudentSurvey(major=" гагнуур ", company_name="Алтан ХХК", env_1=3, recommend_company="Үгүй"),
        StudentSurvey(major="Автомеханик", company_name="Говь ХХК", env_1=4, recommend_company="Тийм"),
        EmployerSurvey(company_name="Төв ХХК", respondent_name="Бат", position="Захирал", phone="99112233",
                       email="a@b.mn", intern_majors="Гагнуур, Автомеханик", q2_1_1=4, rehire_interest="Тийм"),
        EmployerSurvey(company_name="Хуучин ХХК", respondent_name="Бат", position="Захирал", phone="99112233",
                       email="c@d.mn", q2_1_1=5),   # answered before the question existed
    )


def test_major_page_requires_login(client):
    assert client.get("/admin/majors").status_code == 302


def test_major_page_without_data(admin_client):
    assert admin_client.get("/admin/majors").status_code == 200


def test_major_page_groups_both_surveys(app, admin_client):
    _seed(app)
    page = admin_client.get("/admin/majors").get_data(as_text=True)
    assert "Гагнуур" in page and "Автомеханик" in page
    assert "Мэргэжил бичээгүй 1 хариулт" in page            # the legacy employer row is reported, not hidden


def test_analyst_can_view_major_results(app, analyst_client):
    assert analyst_client.get("/admin/majors").status_code == 200


def test_lists_can_be_filtered_by_major(app, admin_client):
    _seed(app)
    page = admin_client.get("/admin/responses/student?major=гагнуур").get_data(as_text=True)
    assert "Эрдэнэ ХХК" in page and "Алтан ХХК" in page and "Говь ХХК" not in page
    page = admin_client.get("/admin/responses/employer?major=автомеханик").get_data(as_text=True)
    assert "Төв ХХК" in page and "Хуучин ХХК" not in page
    # the wildcard characters in the box are literal, not a pattern
    assert "Эрдэнэ ХХК" not in admin_client.get("/admin/responses/student?major=%25").get_data(as_text=True)


def test_response_export_respects_major_filter(app, admin_client):
    _seed(app)
    response = admin_client.get("/admin/export/student/csv?major=автомеханик")
    rows = list(csv.reader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert len(rows) == 2 and "Говь ХХК" in rows[1]


def test_employer_export_contains_the_interns_majors(app, admin_client):
    _seed(app)
    rows = list(csv.reader(io.StringIO(admin_client.get("/admin/export/employer/csv").data.decode("utf-8-sig"))))
    header = "Дадлага хийж буй суралцагчдын мэргэжил"
    assert header in rows[0]
    assert any(row[rows[0].index(header)] == "Гагнуур, Автомеханик" for row in rows[1:])


def test_major_results_excel_export(app, admin_client):
    _seed(app)
    response = admin_client.get("/admin/majors/student/export/xlsx")
    sheet = openpyxl.load_workbook(io.BytesIO(response.data)).active
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0][:3] == ("Мэргэжил", "Хариултын тоо", "Дундаж оноо (1-5)")
    welding = next(r for r in rows[1:] if r[0] == "Гагнуур")
    assert welding[1] == 2 and welding[2] == 4.0


def test_major_results_csv_export_is_formula_safe(app, admin_client):
    add(app, StudentSurvey(major="=EVIL()", company_name="X", env_1=5))
    text = admin_client.get("/admin/majors/student/export/csv").data.decode("utf-8-sig")
    assert list(csv.reader(io.StringIO(text)))[1][0] == "'=EVIL()"


def test_major_export_rejects_unknown_survey_or_format(admin_client):
    assert admin_client.get("/admin/majors/nope/export/csv").status_code == 404
    assert admin_client.get("/admin/majors/student/export/exe").status_code == 404

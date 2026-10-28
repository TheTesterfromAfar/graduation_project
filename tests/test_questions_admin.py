"""Admins editing the survey questions from the web, end to end: editor -> public form -> saved answers."""
import csv
import io
import re

from app.extensions import db
from app.models import EmployerSurvey, StudentSurvey, SurveyConfig
from app.services import stats

from .conftest import count, employer_payload, student_payload

EMPLOYER_GROUP = "graduate_skills"
STUDENT_GROUP = "environment"


def edit(client, survey, action, **data):
    return client.post(f"/admin/questions/{survey}", data={"action": action, **data})


def key_in(response, prefix):
    """The key of the question/group an action just created, read from the redirect's #anchor."""
    return re.search(rf"#{prefix}-([A-Za-z0-9_]+)", response.headers["Location"]).group(1)


def page(client, url):
    response = client.get(url)
    assert response.status_code == 200, url
    return response.get_data(as_text=True)


# ---- access --------------------------------------------------------------------------------
def test_only_admins_can_open_or_use_the_editor(client, admin_client, analyst_client):
    assert client.get("/admin/questions").status_code == 302                     # sent to the login page
    assert client.post("/admin/questions/employer", data={"action": "reset"}).status_code == 302

    for url in ("/admin/questions", "/admin/questions/employer", "/admin/questions/student"):
        assert analyst_client.get(url).status_code == 403                        # read-only role
    assert edit(analyst_client, "employer", "title", title="Хакер").status_code == 403

    for url in ("/admin/questions", "/admin/questions/employer", "/admin/questions/student"):
        assert admin_client.get(url).status_code == 200
    assert admin_client.get("/admin/questions/nope").status_code == 404
    assert edit(admin_client, "nope", "reset").status_code == 404


def test_dashboard_offers_the_editor_to_admins_only(admin_client, analyst_client):
    assert "/admin/questions" in page(admin_client, "/admin/")
    assert "/admin/questions" not in page(analyst_client, "/admin/")


def test_csrf_is_enforced_on_the_editor(app, admin_client):
    app.config["WTF_CSRF_ENABLED"] = True
    assert edit(admin_client, "employer", "title", title="Шинэ").status_code == 400


# ---- defaults ------------------------------------------------------------------------------
def test_surveys_are_unchanged_until_an_admin_edits_them(client):
    employer = page(client, "/employer")
    assert "Ажил олгогчийн сэтгэл ханамжийн судалгаа" in employer
    assert "2.1.1. Мэргэжлийн онолын мэдлэг" in employer
    assert "Дадлага хийх орчин (байр, талбай) тав тухтай байсан уу?" in page(client, "/student")


def test_surveys_fall_back_to_the_defaults_if_the_edits_cannot_be_read(app, client):
    with app.app_context():
        SurveyConfig.__table__.drop(db.engine)       # e.g. a deploy whose migration has not run yet
    assert "2.1.1. Мэргэжлийн онолын мэдлэг" in page(client, "/employer")
    assert client.post("/employer", data=employer_payload()).status_code == 302


# ---- wording, title, choices ---------------------------------------------------------------
def test_reworded_question_and_new_title_appear_on_the_public_form(admin_client, client):
    assert edit(admin_client, "employer", "update_question", key="q2_1_1",
                label="2.1.1. Онолын мэдлэг хэр вэ?", short="Онол").status_code == 302
    assert edit(admin_client, "employer", "title", title="Шинэ гарчигтай судалгаа").status_code == 302

    form = page(client, "/employer")
    assert "2.1.1. Онолын мэдлэг хэр вэ?" in form and "2.1.1. Мэргэжлийн онолын мэдлэг" not in form
    assert "Шинэ гарчигтай судалгаа" in form
    assert "Шинэ гарчигтай судалгаа" in page(client, "/")                       # home page card too

    assert edit(admin_client, "student", "update_question", key="env_1", label="Орчин ямар байсан бэ?").status_code == 302
    assert "Орчин ямар байсан бэ?" in page(client, "/student")
    assert "Шинэ гарчигтай судалгаа" not in page(client, "/student")           # the other survey is untouched


def test_changed_dropdown_choices_are_shown_and_enforced(app, admin_client, client):
    # saved while "Төв" was still offered
    assert client.post("/employer", data=employer_payload(company_name="Old ХХК", aimag_city="Төв")).status_code == 302

    response = edit(admin_client, "employer", "update_field", key="aimag_city",
                    label="1.7. Аймаг, хот", choices="Өвөрхангай\nЭрдэнэт\nБусад")
    assert response.status_code == 302

    form = page(client, "/employer")
    assert "1.7. Аймаг, хот" in form and 'value="Эрдэнэт"' in form and 'value="Улаанбаатар"' not in form

    assert client.post("/employer", data=employer_payload(company_name="New ХХК", aimag_city="Эрдэнэт")).status_code == 302
    assert client.post("/employer", data=employer_payload(aimag_city="Төв")).status_code == 200   # no longer offered
    assert count(app, EmployerSurvey) == 2

    # the admin list can filter by the new choice, and by the old one the earlier response still carries
    new_only = page(admin_client, "/admin/responses/employer?aimag_city=Эрдэнэт")
    assert "New ХХК" in new_only and "Old ХХК" not in new_only
    old_only = page(admin_client, "/admin/responses/employer?aimag_city=Төв")
    assert "Old ХХК" in old_only and "New ХХК" not in old_only


def test_the_answer_counted_as_positive_cannot_be_removed(admin_client, client):
    response = edit(admin_client, "employer", "update_field", key="rehire_interest",
                    label="2.2. Дахин авах уу?", choices="Үгүй\nМагадгүй")
    assert response.status_code == 200
    assert "Тийм" in response.get_data(as_text=True) and "устгах боломжгүй" in response.get_data(as_text=True)
    assert 'value="Тийм"' in page(client, "/employer")                           # nothing was saved


def test_choices_longer_than_the_database_column_are_rejected(app, admin_client):
    response = edit(admin_client, "student", "update_field", key="gender", label="Хүйс",
                    choices="Эрэгтэй\nЭмэгтэй\n" + "ш" * 21)                      # student gender is VARCHAR(20)
    assert response.status_code == 200 and "хэт урт" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.query(SurveyConfig).count() == 0


# ---- adding a question ---------------------------------------------------------------------
def test_added_question_is_asked_stored_shown_exported_and_averaged(app, admin_client, client):
    response = edit(admin_client, "employer", "add_question", key=EMPLOYER_GROUP,
                    label="2.1.10. Шинэ чадвар", short="Шинэ чадвар")
    assert response.status_code == 302
    field = key_in(response, "q")
    assert field.startswith("x_")

    form = page(client, "/employer")
    assert "2.1.10. Шинэ чадвар" in form and f'name="{field}"' in form

    # it is required like every other rating
    missing = client.post("/employer", data=employer_payload())
    assert missing.status_code == 200 and "Үнэлгээгээ сонгоно уу" in missing.get_data(as_text=True)
    assert count(app, EmployerSurvey) == 0

    assert client.post("/employer", data=employer_payload(**{field: "5"})).status_code == 302
    assert client.post("/employer", data=employer_payload(**{field: "6"})).status_code == 200   # out of range
    with app.app_context():
        row = db.session.query(EmployerSurvey).one()
        assert row.extra_answers == {field: 5} and row.q2_1_1 == 4
        assert stats.rating_averages(EmployerSurvey, [field, "q2_1_1"]) == {field: 5.0, "q2_1_1": 4.0}
        record_id = row.id

    detail = page(admin_client, f"/admin/responses/employer/{record_id}")
    assert "2.1.10. Шинэ чадвар" in detail
    assert "Шинэ чадвар" in page(admin_client, "/admin/")
    assert "Шинэ чадвар" in page(admin_client, "/admin/majors")

    rows = list(csv.reader(io.StringIO(admin_client.get("/admin/export/employer/csv").data.decode("utf-8-sig"))))
    assert dict(zip(rows[0], rows[1]))["Шинэ чадвар (1-5)"] == "5"


def test_student_survey_questions_can_be_added_too(app, admin_client, client):
    response = edit(admin_client, "student", "add_question", key=STUDENT_GROUP, label="Багш сайн байсан уу?")
    field = key_in(response, "q")
    assert "Багш сайн байсан уу?" in page(client, "/student")

    assert client.post("/student", data=student_payload()).status_code == 200            # new one unanswered
    assert client.post("/student", data=student_payload(**{field: "3"})).status_code == 302
    with app.app_context():
        row = db.session.query(StudentSurvey).one()
        assert row.extra_answers == {field: 3} and row.env_1 == 5


# ---- hiding, ordering, groups --------------------------------------------------------------
def test_hidden_question_is_not_asked_but_its_answers_are_kept(app, admin_client, client):
    assert client.post("/employer", data=employer_payload()).status_code == 302

    assert edit(admin_client, "employer", "toggle_question", key="q2_1_3").status_code == 302
    assert 'name="q2_1_3"' not in page(client, "/employer")
    without = employer_payload()
    del without["q2_1_3"]
    assert client.post("/employer", data=without).status_code == 302

    with app.app_context():
        old, new = db.session.query(EmployerSurvey).order_by(EmployerSurvey.id).all()
        assert old.q2_1_3 == 4 and new.q2_1_3 is None                                  # data survived

    assert edit(admin_client, "employer", "toggle_question", key="q2_1_3").status_code == 302
    assert 'name="q2_1_3"' in page(client, "/employer")


def test_questions_can_be_reordered(admin_client, client):
    assert edit(admin_client, "employer", "move_question", key="q2_1_2", direction="up").status_code == 302
    form = page(client, "/employer")
    assert form.index('name="q2_1_2"') < form.index('name="q2_1_1"')
    assert edit(admin_client, "employer", "move_question", key="q2_1_2", direction="down").status_code == 302
    form = page(client, "/employer")
    assert form.index('name="q2_1_1"') < form.index('name="q2_1_2"')


def test_a_new_group_needs_a_question_and_can_be_hidden(admin_client, client):
    response = edit(admin_client, "student", "add_group", title="Шинэ бүлэг", hint="1 – муу, 5 – сайн")
    group = key_in(response, "g")
    assert "Шинэ бүлэг" not in page(client, "/student")                                  # empty groups are not shown

    edit(admin_client, "student", "add_question", key=group, label="Бүлгийн асуулт")
    form = page(client, "/student")
    assert "Шинэ бүлэг" in form and "Бүлгийн асуулт" in form and "1 – муу, 5 – сайн" in form

    edit(admin_client, "student", "toggle_group", key=group)
    assert "Шинэ бүлэг" not in page(client, "/student")


# ---- mistakes ------------------------------------------------------------------------------
def test_a_rejected_edit_shows_the_message_and_keeps_what_was_typed(app, admin_client, client):
    too_long = "x" * 301
    response = edit(admin_client, "employer", "update_question", key="q2_1_1", label=too_long)
    body = response.get_data(as_text=True)
    assert response.status_code == 200 and "хамгийн ихдээ 300" in body and too_long in body
    assert "2.1.1. Мэргэжлийн онолын мэдлэг" in page(client, "/employer")             # nothing changed
    assert count(app, SurveyConfig) == 0


def test_unknown_actions_and_questions_are_rejected(app, admin_client):
    assert edit(admin_client, "employer", "drop_database").status_code == 200
    assert edit(admin_client, "employer", "update_question", key="nope", label="x").status_code == 200
    assert edit(admin_client, "employer", "update_field", key="id", label="x").status_code == 200   # not a form question
    assert edit(admin_client, "employer", "move_question", key="q2_1_1", direction="sideways").status_code == 200
    assert count(app, SurveyConfig) == 0


def test_export_headers_cannot_carry_formulas(admin_client):
    edit(admin_client, "employer", "update_question", key="q2_1_1", label="Асуулт", short="=SUM(A1)")
    rows = list(csv.reader(io.StringIO(admin_client.get("/admin/export/employer/csv").data.decode("utf-8-sig"))))
    assert "'=SUM(A1) (1-5)" in rows[0]


# ---- reset ---------------------------------------------------------------------------------
def test_reset_brings_back_the_original_questions_and_keeps_the_answers(app, admin_client, client):
    response = edit(admin_client, "employer", "add_question", key=EMPLOYER_GROUP, label="Нэмэлт асуулт")
    field = key_in(response, "q")
    edit(admin_client, "employer", "update_question", key="q2_1_1", label="Өөрчилсөн")
    client.post("/employer", data=employer_payload(**{field: "2"}))
    assert count(app, SurveyConfig) == 1

    assert edit(admin_client, "employer", "reset").status_code == 302
    form = page(client, "/employer")
    assert "2.1.1. Мэргэжлийн онолын мэдлэг" in form and "Нэмэлт асуулт" not in form
    assert count(app, SurveyConfig) == 0
    assert count(app, EmployerSurvey) == 1                                              # responses are never deleted

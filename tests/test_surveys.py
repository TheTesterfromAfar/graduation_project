from app.extensions import db
from app.models import EmployerSurvey, StudentSurvey

from .conftest import count, employer_payload, student_payload


def test_public_pages_load(client):
    for url in ("/", "/employer", "/student", "/success", "/login", "/healthz"):
        assert client.get(url).status_code == 200


def test_employer_submission_is_saved_and_normalised(app, client):
    response = client.post("/employer", data=employer_payload())
    assert response.status_code == 302 and "/success" in response.headers["Location"]
    with app.app_context():
        row = db.session.query(EmployerSurvey).one()
        assert row.email == "bat@example.mn"          # lower-cased
        assert row.q2_1_1 == 4
        assert row.property_form is None               # blank optional select stored as NULL, not ''


def test_employer_must_name_the_interns_majors(app, client):
    response = client.post("/employer", data=employer_payload(intern_majors=""))
    assert response.status_code == 200
    assert "Энэ талбарыг бөглөнө үү" in response.get_data(as_text=True)
    assert client.post("/employer", data=employer_payload(intern_majors="x" * 501)).status_code == 200
    assert count(app, EmployerSurvey) == 0


def test_employer_interns_majors_are_saved(app, client):
    client.post("/employer", data=employer_payload(intern_majors="  Гагнуур,\nАвтомеханик "))
    with app.app_context():
        assert db.session.query(EmployerSurvey).one().intern_majors == "Гагнуур,\nАвтомеханик"


def test_missing_rating_is_rejected_with_message(app, client):
    payload = employer_payload()
    del payload["q2_1_3"]
    response = client.post("/employer", data=payload)
    assert response.status_code == 200
    assert "Үнэлгээгээ сонгоно уу" in response.get_data(as_text=True)
    assert count(app, EmployerSurvey) == 0


def test_out_of_range_rating_is_rejected(app, client):
    assert client.post("/employer", data=employer_payload(q2_1_1="6")).status_code == 200
    assert client.post("/employer", data=employer_payload(q2_1_1="abc")).status_code == 200
    assert count(app, EmployerSurvey) == 0


def test_value_outside_choices_is_rejected(app, client):
    client.post("/employer", data=employer_payload(aimag_city="<script>"))
    assert count(app, EmployerSurvey) == 0


def test_invalid_email_and_phone_are_rejected(app, client):
    client.post("/employer", data=employer_payload(email="not-an-email"))
    client.post("/employer", data=employer_payload(phone="abc"))
    assert count(app, EmployerSurvey) == 0


def test_overlong_text_is_rejected(app, client):
    client.post("/employer", data=employer_payload(company_name="x" * 201))
    assert count(app, EmployerSurvey) == 0


def test_student_submission_leaves_unasked_columns_null(app, client):
    assert client.post("/student", data=student_payload()).status_code == 302
    with app.app_context():
        row = db.session.query(StudentSurvey).one()
        assert row.env_1 == 5 and row.age == 19
        assert row.soft_1 is None and row.tech_1 is None and row.quality_1 is None  # not 0


def test_student_age_must_be_sensible(app, client):
    client.post("/student", data=student_payload(age="3"))
    client.post("/student", data=student_payload(age="abc"))
    assert count(app, StudentSurvey) == 0


def test_honeypot_discards_bot_submissions_silently(app, client):
    response = client.post("/employer", data=employer_payload(website="http://spam.example"))
    assert response.status_code == 302            # looks like success to the bot
    assert count(app, EmployerSurvey) == 0


def test_success_page_ignores_unknown_survey_type(client):
    assert client.get("/success?survey_type=<script>").status_code == 200


def test_csrf_is_enforced_when_enabled(app, client):
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/employer", data=employer_payload()).status_code == 400
    assert count(app, EmployerSurvey) == 0


def test_security_headers_present(client):
    headers = client.get("/").headers
    assert "default-src 'self'" in headers["Content-Security-Policy"]
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"

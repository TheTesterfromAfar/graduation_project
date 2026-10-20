from app.extensions import db
from app.models import EmployerSurvey, User

from .conftest import PASSWORD, add, count, first_id, login, make_user


def one_response():
    return EmployerSurvey(company_name="A", respondent_name="B", position="C", phone="1", email="a@b.mn")


def test_admin_area_requires_login(client):
    response = client.get("/admin/")
    assert response.status_code == 302 and "/login" in response.headers["Location"]
    assert client.get("/admin/responses/employer").status_code == 302
    assert client.get("/admin/export/employer/csv").status_code == 302


def test_login_success_and_redirect(client, admin):
    response = login(client, admin.email)
    assert response.status_code == 302 and response.headers["Location"].endswith("/admin/")
    assert client.get("/admin/").status_code == 200


def test_login_failure_messages_do_not_reveal_which_part_was_wrong(client, admin):
    wrong_password = login(client, admin.email, "wrong-password-123").get_data(as_text=True)
    unknown_user = login(client, "nobody@example.com", "wrong-password-123").get_data(as_text=True)
    assert "И-мэйл эсвэл нууц үг буруу байна." in wrong_password
    assert "И-мэйл эсвэл нууц үг буруу байна." in unknown_user


def test_disabled_account_cannot_log_in(app, client):
    make_user(app, "off@example.com", active=False)
    assert login(client, "off@example.com").status_code == 200
    assert client.get("/admin/").status_code == 302


def test_next_parameter_cannot_redirect_off_site(client, admin):
    for evil in ("//evil.example", "https://evil.example", "/\\evil.example"):
        client.post("/logout")
        response = login(client, admin.email, next=evil)
        assert response.status_code == 302
        assert "evil.example" not in response.headers["Location"]


def test_next_parameter_allows_local_paths(client, admin):
    response = login(client, admin.email, next="/admin/responses/student")
    assert response.headers["Location"].endswith("/admin/responses/student")


def test_logout_requires_post_and_ends_the_session(client, admin):
    login(client, admin.email)
    assert client.get("/logout").status_code == 405
    assert client.post("/logout").status_code == 302
    assert client.get("/admin/").status_code == 302


def test_passwords_are_hashed(app, admin):
    with app.app_context():
        user = db.session.query(User).filter_by(email=admin.email).one()
        assert user.password_hash and PASSWORD not in user.password_hash
        assert user.check_password(PASSWORD) and not user.check_password("nope")
        assert not User(email="x@example.com").check_password("anything")  # Google-only account


def test_google_routes_are_hidden_when_not_configured(client):
    assert client.get("/login/google").status_code == 404
    assert client.get("/auth/google/callback").status_code == 404


def test_analyst_is_read_only(app, analyst_client):
    add(app, one_response())
    row_id = first_id(app, EmployerSurvey)

    assert analyst_client.get("/admin/").status_code == 200
    assert analyst_client.get(f"/admin/responses/employer/{row_id}").status_code == 200
    assert analyst_client.get("/admin/export/employer/csv").status_code == 200
    assert analyst_client.post(f"/admin/responses/employer/{row_id}/delete").status_code == 403
    assert analyst_client.post("/admin/data/add", data={"text_content": "[]"}).status_code == 403
    assert count(app, EmployerSurvey) == 1


def test_admin_can_delete(app, admin_client):
    add(app, one_response())
    row_id = first_id(app, EmployerSurvey)
    assert admin_client.post(f"/admin/responses/employer/{row_id}/delete").status_code == 302
    assert count(app, EmployerSurvey) == 0


def test_state_changing_admin_routes_reject_get(admin_client):
    assert admin_client.get("/admin/responses/employer/1/delete").status_code == 405


def test_csrf_protects_admin_posts(app, admin_client):
    app.config["WTF_CSRF_ENABLED"] = True
    assert admin_client.post("/admin/responses/employer/1/delete").status_code == 400
    assert admin_client.post("/logout").status_code == 400

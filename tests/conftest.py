"""Shared fixtures.

Important: the `app` fixture does NOT keep an application context open. Flask reuses an existing app
context for test-client requests, which would make `flask.g` (where Flask-Login caches the current
user) leak between requests. Tests touch the database through the small helpers below instead.
"""
from types import SimpleNamespace

import pytest

from app import create_app
from app.extensions import db
from app.models import ROLE_ADMIN, ROLE_ANALYST, User
from app.questions import EMPLOYER, STUDENT

PASSWORD = "correct horse battery staple"


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


# ---- database helpers (each opens its own short-lived app context) -------------------------
def add(app, *objects):
    with app.app_context():
        db.session.add_all(objects)
        db.session.commit()


def count(app, model):
    with app.app_context():
        return db.session.query(model).count()


def first_id(app, model):
    with app.app_context():
        return db.session.query(model).order_by(model.id).first().id


def attribute(app, model, object_id, name):
    with app.app_context():
        return getattr(db.session.get(model, object_id), name)


def make_user(app, email="admin@example.com", role=ROLE_ADMIN, password=PASSWORD, active=True):
    with app.app_context():
        user = User(email=email, role=role, active=active)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
    return SimpleNamespace(email=email, password=password)


@pytest.fixture()
def admin(app):
    return make_user(app, "admin@example.com", ROLE_ADMIN)


@pytest.fixture()
def analyst(app):
    return make_user(app, "analyst@example.com", ROLE_ANALYST)


# ---- authentication helpers -------------------------------------------------------------
def login(client, email, password=PASSWORD, **extra):
    return client.post("/login", data={"email": email, "password": password, **extra})


@pytest.fixture()
def admin_client(app, admin):
    client = app.test_client()
    assert login(client, admin.email).status_code == 302
    return client


@pytest.fixture()
def analyst_client(app, analyst):
    client = app.test_client()
    assert login(client, analyst.email).status_code == 302
    return client


# ---- form payloads ----------------------------------------------------------------------
def employer_payload(**overrides):
    data = {
        "company_name": "Тест ХХК", "respondent_name": "Бат", "position": "Захирал",
        "phone": "99112233", "email": "Bat@Example.mn", "aimag_city": "Өвөрхангай",
        "rehire_interest": "Тийм", "intern_majors": "Гагнуур, Автомеханик",
    }
    data.update({field: "4" for field in EMPLOYER.rating_fields})
    data.update(overrides)
    return data


def student_payload(**overrides):
    data = {
        "major": "Гагнуур", "company_name": "Эрдэнэт ХХК", "recommend_company": "Тийм",
        "received_salary": "Үгүй", "job_offer_received": "Үгүй", "age": "19",
    }
    data.update({field: "5" for field in STUDENT.rating_fields})
    data.update(overrides)
    return data

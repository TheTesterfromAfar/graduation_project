"""Database models.

Survey table and column names are unchanged from the original prototype, so an existing
database can be adopted with `flask db stamp 0001_initial_schema` (see README).
"""
from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager

ROLE_ADMIN = "admin"      # full access: view, export, delete responses, manage JSON data
ROLE_ANALYST = "analyst"  # read-only: dashboard, search/filter, export
ROLES = (ROLE_ADMIN, ROLE_ANALYST)


def utcnow():
    """Naive UTC timestamp (the column convention used since the original prototype)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------------------
_dummy_hash = None


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(120))
    # NULL for accounts that only sign in with Google.
    password_hash = db.Column(db.String(255))
    role = db.Column(db.String(20), nullable=False, default=ROLE_ANALYST)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime)

    @property
    def is_active(self):  # Flask-Login hook: inactive users can't log in or keep a session
        return bool(self.active)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    def set_password(self, password):
        # Werkzeug's default is a salted, memory-hard scrypt hash.
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def burn_password_check(password):
        """Spend the same time as a real check when the email is unknown (no timing oracle)."""
        global _dummy_hash
        if _dummy_hash is None:
            _dummy_hash = generate_password_hash("not-a-real-password")
        check_password_hash(_dummy_hash, password)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------------------
# Survey responses
# --------------------------------------------------------------------------------------
class EmployerSurvey(db.Model):
    __tablename__ = "employer_responses"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=utcnow, index=True)

    company_name = db.Column(db.String(200), nullable=False)
    respondent_name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    reg_number = db.Column(db.String(50))
    aimag_city = db.Column(db.String(100))
    sum_district = db.Column(db.String(100))
    legal_form = db.Column(db.String(100))
    property_form = db.Column(db.String(100))
    economic_sector = db.Column(db.String(200))
    employee_count = db.Column(db.String(50))

    q2_1_1 = db.Column(db.Integer)
    q2_1_2 = db.Column(db.Integer)
    q2_1_3 = db.Column(db.Integer)
    q2_1_4 = db.Column(db.Integer)
    q2_1_5 = db.Column(db.Integer)
    q2_1_6 = db.Column(db.Integer)
    q2_1_7 = db.Column(db.Integer)
    q2_1_8 = db.Column(db.Integer)
    q2_1_9 = db.Column(db.Integer)

    rehire_interest = db.Column(db.String(50))

    def __repr__(self):
        return f"<EmployerSurvey {self.id} {self.company_name!r}>"


class StudentSurvey(db.Model):
    __tablename__ = "student_responses"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=utcnow, index=True)

    gender = db.Column(db.String(20))
    age = db.Column(db.Integer)
    major = db.Column(db.String(150), nullable=False)
    study_type = db.Column(db.String(100))
    company_name = db.Column(db.String(200), nullable=False)

    env_1 = db.Column(db.Integer)
    env_2 = db.Column(db.Integer)
    env_3 = db.Column(db.Integer)
    env_4 = db.Column(db.Integer)
    env_5 = db.Column(db.Integer)
    env_6 = db.Column(db.Integer)
    env_7 = db.Column(db.Integer)

    # soft_*, tech_* and quality_* are not asked by the current form (see app/questions.py);
    # they stay NULL until those questions are added.
    soft_1 = db.Column(db.Integer)
    soft_2 = db.Column(db.Integer)
    soft_3 = db.Column(db.Integer)
    soft_4 = db.Column(db.Integer)
    soft_5 = db.Column(db.Integer)
    soft_6 = db.Column(db.Integer)
    soft_7 = db.Column(db.Integer)

    tech_1 = db.Column(db.Integer)
    tech_2 = db.Column(db.Integer)
    tech_3 = db.Column(db.Integer)
    tech_4 = db.Column(db.Integer)
    tech_5 = db.Column(db.Integer)

    quality_1 = db.Column(db.Integer)
    quality_2 = db.Column(db.Integer)

    recommend_company = db.Column(db.String(50))
    received_salary = db.Column(db.String(50))
    daily_salary_amount = db.Column(db.String(50))
    job_offer_received = db.Column(db.String(50))
    job_offer_details = db.Column(db.Text)

    def __repr__(self):
        return f"<StudentSurvey {self.id} {self.major!r}>"


SURVEY_MODELS = {"employer": EmployerSurvey, "student": StudentSurvey}


class AdminDataEntry(db.Model):
    """JSON documents uploaded or pasted by an admin."""

    __tablename__ = "admin_data_entries"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(150), nullable=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=utcnow)

    @property
    def size(self):
        return len(self.content or "")

"""Flask-WTF forms. Survey forms are assembled from app/questions.py."""
import json

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (EmailField, HiddenField, IntegerField, PasswordField, RadioField,
                     SelectField, StringField, TelField, TextAreaField)
from wtforms.validators import (AnyOf, DataRequired, Email, InputRequired, Length, NumberRange,
                                Optional, Regexp, ValidationError)

from . import questions as q

MSG_REQUIRED = "Энэ талбарыг бөглөнө үү."
MSG_CHOICE = "Жагсаалтаас сонгоно уу."
MSG_RATING = "Үнэлгээгээ сонгоно уу."
MSG_MAX_LEN = "Хамгийн ихдээ %(max)d тэмдэгт оруулна уу."


class _MongolianTranslations:
    """Replaces WTForms' English fallback messages so every error shown is in Mongolian."""

    MESSAGES = {
        "This field is required.": MSG_REQUIRED,
        "Invalid email address.": "И-мэйл хаяг буруу байна.",
        "Invalid input.": "Буруу утга оруулсан байна.",
        "Not a valid integer value.": "Бүхэл тоо оруулна уу.",
        "Not a valid choice.": MSG_CHOICE,
        "Invalid Choice: could not coerce.": MSG_CHOICE,
        "Invalid value, must be one of: %(values)s.": MSG_CHOICE,
        "Number must be at least %(min)s.": "Тоо хамгийн багадаа %(min)s байх ёстой.",
        "Number must be at most %(max)s.": "Тоо хамгийн ихдээ %(max)s байх ёстой.",
        "Number must be between %(min)s and %(max)s.": "Тоо %(min)s-аас %(max)s хооронд байх ёстой.",
        "Field must be at least %(min)d character long.": "Хамгийн багадаа %(min)d тэмдэгт оруулна уу.",
        "Field must be at least %(min)d characters long.": "Хамгийн багадаа %(min)d тэмдэгт оруулна уу.",
        "Field cannot be longer than %(max)d character.": MSG_MAX_LEN,
        "Field cannot be longer than %(max)d characters.": MSG_MAX_LEN,
        "Field must be between %(min)d and %(max)d characters long.": "%(min)d-%(max)d тэмдэгт оруулна уу.",
        "CSRF token missing.": "Хуудасны аюулгүй байдлын токен дутуу байна. Хуудсаа дахин ачаална уу.",
        "CSRF failed.": "Хуудасны аюулгүй байдлын шалгалт амжилтгүй боллоо. Хуудсаа дахин ачаална уу.",
    }

    def gettext(self, string):
        return self.MESSAGES.get(string, string)

    def ngettext(self, singular, plural, n):
        return self.gettext(singular if n == 1 else plural)


_TRANSLATIONS = _MongolianTranslations()


class BaseForm(FlaskForm):
    class Meta:
        def get_translations(self, form):
            return _TRANSLATIONS


def _strip(value):
    return value.strip() if isinstance(value, str) else value


def _lower_strip(value):
    return value.strip().lower() if isinstance(value, str) else value


def _text(label, max_len, required=False, **kwargs):
    validators = [DataRequired(MSG_REQUIRED) if required else Optional(), Length(max=max_len, message=MSG_MAX_LEN)]
    return StringField(label, filters=[_strip], validators=validators, **kwargs)


def _select(label, values, required=False):
    """Dropdown with an explicit blank first option, so skipping a question never records the first answer."""
    values = tuple(values)
    choices = [("", "— Сонгоно уу —")] + [(v, v) for v in values]
    validators = [DataRequired(MSG_CHOICE) if required else Optional(), AnyOf(values, message=MSG_CHOICE)]
    # validate_choice=False: AnyOf above gives a single, localised message instead of two.
    return SelectField(label, choices=choices, default="", validate_choice=False, validators=validators)


def _rating(label):
    return RadioField(
        label,
        choices=[(i, str(i)) for i in q.RATING_SCALE],
        coerce=int,
        validate_choice=False,
        validators=[InputRequired(MSG_RATING), AnyOf(q.RATING_SCALE, message=MSG_RATING)],
    )


PHONE_RE = r"^\+?[0-9][0-9\s\-()]{5,19}$"
REG_NUMBER_RE = r"^[\w\-]{4,20}$"
MONEY_RE = r"^[0-9][0-9\s,.']{0,19}$"


# --------------------------------------------------------------------------------------
# Public surveys
# --------------------------------------------------------------------------------------
class SurveyForm(BaseForm):
    # Honeypot: invisible to people (hidden with CSS), tempting to bots. Checked in the view.
    website = StringField("Website", filters=[_strip])


class EmployerSurveyForm(SurveyForm):
    company_name = _text("1.1. Байгууллагын нэр", 200, required=True)
    respondent_name = _text("1.2. Таны нэр", 100, required=True)
    position = _text("1.3. Таны албан тушаал", 100, required=True)
    phone = TelField(
        "1.4. Утасны дугаар",
        filters=[_strip],
        validators=[DataRequired(MSG_REQUIRED),
                    Regexp(PHONE_RE, message="Утасны дугаар буруу байна. Жишээ: 99112233 эсвэл +976 99112233")],
    )
    email = EmailField(
        "1.5. И-мэйл хаяг",
        filters=[_lower_strip],
        validators=[DataRequired(MSG_REQUIRED), Email(), Length(max=100, message=MSG_MAX_LEN)],
    )
    reg_number = StringField(
        "1.6. Байгууллагын регистрийн дугаар",
        filters=[_strip],
        validators=[Optional(), Regexp(REG_NUMBER_RE, message="Регистрийн дугаар буруу байна (4-20 тэмдэгт).")],
    )
    aimag_city = _select("1.7. Байршил (Аймаг / Хот)", q.AIMAG_CITY)
    sum_district = _text("Сум / Дүүрэг", 100)
    legal_form = _select("1.8. Хариуцлагын хэлбэр", q.LEGAL_FORM)
    property_form = _select("1.9. Өмчийн хэлбэр", q.PROPERTY_FORM)
    economic_sector = _text("1.10. Эдийн засгийн салбар", 200)
    employee_count = _select("1.11. Ажилтны тоо", q.EMPLOYEE_COUNT)
    intern_majors = TextAreaField(
        "1.12. Танай байгууллагад ямар мэргэжлийн суралцагчид дадлага хийж байна вэ?",
        filters=[_strip],
        validators=[DataRequired(MSG_REQUIRED), Length(max=500, message=MSG_MAX_LEN)],
    )
    rehire_interest = _select(
        "2.2. Та энэ сургалтын байгууллагын төгсөгчийг дахин ажилд авах сонирхолтой байна уу?",
        q.REHIRE_INTEREST,
        required=True,
    )


class StudentSurveyForm(SurveyForm):
    gender = _select("1.1. Хүйс", q.GENDER)
    age = IntegerField(
        "1.2. Нас",
        validators=[Optional(), NumberRange(14, 70, message="Нас %(min)s-%(max)s хооронд байх ёстой.")],
    )
    major = _text("1.3. Суралцаж буй мэргэжил", 150, required=True)
    study_type = _select("1.4. Суралцаж буй хэлбэр", q.STUDY_TYPE)
    company_name = _text("1.5. Дадлага хийсэн байгууллагын нэр", 200, required=True)
    recommend_company = _select("3.1 Та энэ байгууллагад дахин дадлага хийхийг санал болгох уу?", q.RECOMMEND, required=True)
    received_salary = _select("3.2 Цалин хөлс олгосон уу?", q.YES_NO, required=True)
    daily_salary_amount = StringField(
        "Өдрийн дундаж цалин (хэрэв олгосон бол)",
        filters=[_strip],
        validators=[Optional(), Regexp(MONEY_RE, message="Зөвхөн тоогоор бичнэ үү. Жишээ: 50000")],
    )
    job_offer_received = _select("3.3 Ажлын байрны санал авсан уу?", q.YES_NO, required=True)
    job_offer_details = TextAreaField(
        "3.4 Тийм бол ямар ажлын байранд, ямар ААНБ-д болохыг бичнэ үү",
        filters=[_strip],
        validators=[Optional(), Length(max=1000, message=MSG_MAX_LEN)],
    )


# Rating questions are generated from the survey definitions (documented WTForms dynamic-form pattern).
for _form, _spec in ((EmployerSurveyForm, q.EMPLOYER), (StudentSurveyForm, q.STUDENT)):
    for _question in _spec.rating_questions:
        setattr(_form, _question.field, _rating(_question.label))

SURVEY_FORMS = {"employer": EmployerSurveyForm, "student": StudentSurveyForm}


# --------------------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------------------
class LoginForm(BaseForm):
    email = EmailField(
        "И-мэйл хаяг",
        filters=[_lower_strip],
        validators=[DataRequired(MSG_REQUIRED), Email(), Length(max=255, message=MSG_MAX_LEN)],
    )
    password = PasswordField("Нууц үг", validators=[DataRequired(MSG_REQUIRED), Length(max=128, message=MSG_MAX_LEN)])
    next = HiddenField()


# --------------------------------------------------------------------------------------
# Admin JSON data
# --------------------------------------------------------------------------------------
def _check_json(text):
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Хүчинтэй JSON биш байна (мөр {exc.lineno}, багана {exc.colno}).") from exc
    except RecursionError as exc:
        raise ValidationError("JSON хэт гүн давхарласан байна.") from exc


class AdminDataForm(BaseForm):
    json_file = FileField("JSON файл оруулах (.json)", validators=[FileAllowed(["json"], "Зөвхөн .json файл оруулна уу.")])
    text_content = TextAreaField("Эсвэл JSON өгөгдлийг шууд хуулж тавих", filters=[_strip])

    filename = None   # set by validate()
    content = None    # set by validate()

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators=extra_validators):
            return False

        upload = self.json_file.data
        if upload:
            try:
                text = upload.read().decode("utf-8-sig")  # tolerate the BOM Windows editors add
            except UnicodeDecodeError:
                self.json_file.errors.append("Файл UTF-8 кодчилолтой байх ёстой.")
                return False
            self.filename = (upload.filename or "upload.json")[:150]
        elif self.text_content.data:
            text = self.text_content.data
            self.filename = "Manual Text Input"
        else:
            self.text_content.errors.append("Файл эсвэл текст оруулна уу.")
            return False

        try:
            _check_json(text)
        except ValidationError as exc:
            (self.json_file if upload else self.text_content).errors.append(str(exc))
            return False

        self.content = text
        return True


class AdminDataEditForm(BaseForm):
    content = TextAreaField(
        "JSON агуулга",
        filters=[_strip],
        validators=[DataRequired(MSG_REQUIRED)],
    )

    def validate_content(self, field):
        _check_json(field.data)

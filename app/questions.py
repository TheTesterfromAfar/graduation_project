"""Survey definitions: the single source of truth for forms, detail pages, filters and exports.

Pure data - no Flask or SQLAlchemy imports. To add a rating question, append a `Question` to a
group below (the field name must also exist as a column on the model, then run
`flask db migrate`). The form, admin detail page, dashboard and CSV/Excel export pick it up
automatically.
"""
from dataclasses import dataclass
from typing import Tuple

RATING_SCALE = (1, 2, 3, 4, 5)


@dataclass(frozen=True)
class Question:
    field: str   # model column / form field name
    label: str   # full question text shown to respondents
    short: str   # compact label for exports and admin tables


@dataclass(frozen=True)
class RatingGroup:
    key: str
    title: str
    questions: Tuple[Question, ...]
    hint: str = ""


@dataclass(frozen=True)
class FilterOption:
    name: str
    label: str
    choices: Tuple[str, ...]


@dataclass(frozen=True)
class SurveySpec:
    key: str
    title: str
    short_title: str
    icon: str
    leading_fields: Tuple[Tuple[str, str], ...]    # (column, label) before the ratings
    rating_groups: Tuple[RatingGroup, ...]
    trailing_fields: Tuple[Tuple[str, str], ...]   # (column, label) after the ratings
    filters: Tuple[FilterOption, ...]
    search_fields: Tuple[str, ...]
    list_columns: Tuple[Tuple[str, str], ...]
    name_field: str                                # used for "sort by name"
    distribution_fields: Tuple[Tuple[str, str], ...]

    @property
    def rating_questions(self):
        return tuple(q for group in self.rating_groups for q in group.questions)

    @property
    def rating_fields(self):
        return tuple(q.field for q in self.rating_questions)

    @property
    def export_columns(self):
        """(column, header) pairs, in export order."""
        return (
            (("timestamp", "Огноо"),)
            + self.leading_fields
            + tuple((q.field, f"{q.short} (1-5)") for q in self.rating_questions)
            + self.trailing_fields
        )

    @property
    def filter_map(self):
        return {f.name: f for f in self.filters}


# --------------------------------------------------------------------------------------
# Answer choices
# --------------------------------------------------------------------------------------
AIMAG_CITY = ("Өвөрхангай", "Улаанбаатар", "Булган", "Төв", "Бусад")
LEGAL_FORM = ("Компани", "Төсвийн байгууллага", "ТӨҮГ/ОНӨҮГ", "Нөхөрлөл", "НҮТББ", "Хувийн хэвшил")
# NOTE: the original form never asked 1.9 (property form) / 1.10 (economic sector) although the
# columns exist and the numbering skips them. These options are a proposal - please verify them
# against your questionnaire.
PROPERTY_FORM = ("Төрийн өмч", "Хувийн өмч", "Төр хувийн хэвшлийн хамтарсан", "Гадаадын хөрөнгө оруулалттай")
EMPLOYEE_COUNT = ("1-9", "10-19", "20-49", "50 ба түүнээс дээш")
REHIRE_INTEREST = ("Тийм", "Үгүй", "Магадгүй")

GENDER = ("Эрэгтэй", "Эмэгтэй")
STUDY_TYPE = ("МБС 3 жил", "МБС 1 жил", "Техникийн боловсрол")
RECOMMEND = ("Тийм", "Зарим талаараа", "Үгүй")
YES_NO = ("Тийм", "Үгүй")


# --------------------------------------------------------------------------------------
# Employer survey
# --------------------------------------------------------------------------------------
EMPLOYER = SurveySpec(
    key="employer",
    title="Ажил олгогчийн сэтгэл ханамжийн судалгаа",
    short_title="Ажил олгогч",
    icon="briefcase",
    leading_fields=(
        ("company_name", "Байгууллагын нэр"),
        ("reg_number", "Регистр"),
        ("respondent_name", "Нэр"),
        ("position", "Албан тушаал"),
        ("phone", "Утас"),
        ("email", "И-мэйл"),
        ("aimag_city", "Аймаг/Хот"),
        ("sum_district", "Сум/Дүүрэг"),
        ("legal_form", "Хариуцлагын хэлбэр"),
        ("property_form", "Өмчийн хэлбэр"),
        ("economic_sector", "Эдийн засгийн салбар"),
        ("employee_count", "Ажилтны тоо"),
    ),
    rating_groups=(
        RatingGroup(
            key="graduate_skills",
            title="Төгсөгчийн ур чадварын үнэлгээ",
            hint="1: Маш муу | 2: Муу | 3: Дунд | 4: Сайн | 5: Маш сайн",
            questions=(
                Question("q2_1_1", "2.1.1. Мэргэжлийн онолын мэдлэг", "Онолын мэдлэг"),
                Question("q2_1_2", "2.1.2. Ажлын байрны технологи, тоног төхөөрөмж зөв ашиглах", "Тоног төхөөрөмж ашиглах"),
                Question("q2_1_3", "2.1.3. Мэргэжлийн стандарт, аюулгүй ажиллагааны мөрдөлт", "Аюулгүй ажиллагаа"),
                Question("q2_1_4", "2.1.4. Бусдыг хүндэлж харьцах", "Бусдыг хүндлэх"),
                Question("q2_1_5", "2.1.5. Хариуцлагатай байдал", "Хариуцлагатай байдал"),
                Question("q2_1_6", "2.1.6. Үнэнч шударга байдал", "Үнэнч шударга"),
                Question("q2_1_7", "2.1.7. Багаар ажиллах чадвар", "Багаар ажиллах"),
                Question("q2_1_8", "2.1.8. Цаг баримтлах", "Цаг баримтлах"),
                Question("q2_1_9", "2.1.9. Идэвх санаачилга", "Идэвх санаачилга"),
            ),
        ),
    ),
    trailing_fields=(("rehire_interest", "Дахин ажилд авах сонирхол"),),
    filters=(
        FilterOption("aimag_city", "Аймаг/Хот", AIMAG_CITY),
        FilterOption("legal_form", "Хариуцлагын хэлбэр", LEGAL_FORM),
        FilterOption("employee_count", "Ажилтны тоо", EMPLOYEE_COUNT),
        FilterOption("rehire_interest", "Дахин ажилд авах сонирхол", REHIRE_INTEREST),
    ),
    search_fields=("company_name", "respondent_name", "position", "email", "phone",
                   "reg_number", "sum_district", "economic_sector"),
    list_columns=(
        ("timestamp", "Огноо"),
        ("company_name", "Байгууллага"),
        ("respondent_name", "Хариуцагч"),
        ("aimag_city", "Аймаг/Хот"),
        ("phone", "Утас"),
    ),
    name_field="company_name",
    distribution_fields=(
        ("rehire_interest", "Дахин ажилд авах сонирхол"),
        ("aimag_city", "Аймаг/Хот"),
        ("legal_form", "Хариуцлагын хэлбэр"),
        ("employee_count", "Ажилтны тоо"),
    ),
)


# --------------------------------------------------------------------------------------
# Student (intern) survey
# --------------------------------------------------------------------------------------
# The model also has soft_1..7, tech_1..5 and quality_1..2 columns, but the original form never
# asked those questions. To start collecting them, add a RatingGroup here, e.g.
#     RatingGroup("soft_skills", "Зөөлөн ур чадвар", (Question("soft_1", "<question text>", "<short>"), ...))
STUDENT = SurveySpec(
    key="student",
    title="Үйлдвэрлэлийн дадлага хийж буй суралцагчийн сэтгэл ханамжийн судалгаа",
    short_title="Дадлагажигч суралцагч",
    icon="book",
    leading_fields=(
        ("gender", "Хүйс"),
        ("age", "Нас"),
        ("major", "Мэргэжил"),
        ("study_type", "Суралцаж буй хэлбэр"),
        ("company_name", "Дадлага хийсэн ААНБ"),
    ),
    rating_groups=(
        RatingGroup(
            key="environment",
            title="Дадлагын орчин ба багшийн удирдамжийн үнэлгээ",
            hint="1 – хамгийн бага үнэлгээ, 5 – хамгийн өндөр үнэлгээ",
            questions=(
                Question("env_1", "Дадлага хийх орчин (байр, талбай) тав тухтай байсан уу?", "Дадлагын орчин"),
                Question("env_2", "Аюулгүй ажиллагааны зааварчилгаа хангалттай өгсөн үү?", "Аюулгүй ажиллагааны зааварчилгаа"),
                Question("env_3", "Хөдөлмөр хамгааллын хувцас, хэрэгслийг бүрэн өмсөж хэрэглэсэн үү?", "Хөдөлмөр хамгааллын хэрэгсэл"),
                Question("env_4", "Ажлын багаж, тоног төхөөрөмж хүртээмжтэй байсан уу?", "Багаж, тоног төхөөрөмжийн хүртээмж"),
                Question("env_5", "Дадлага удирдсан багшийн хариуцлага, ажилласан байдал", "Багшийн хариуцлага"),
                Question("env_6", "Дадлага удирдсан багш тогтмол зөвлөгөө өгч байсан уу?", "Багшийн тогтмол зөвлөгөө"),
                Question("env_7", "Шаардлагатай үед дэмжлэг үзүүлсэн үү?", "Шаардлагатай үеийн дэмжлэг"),
            ),
        ),
    ),
    trailing_fields=(
        ("recommend_company", "Дахин дадлага хийх санал"),
        ("received_salary", "Цалин хөлс авсан уу"),
        ("daily_salary_amount", "Өдрийн цалингийн хэмжээ"),
        ("job_offer_received", "Ажлын байрны санал авсан уу"),
        ("job_offer_details", "Ажлын байрны дэлгэрэнгүй"),
    ),
    filters=(
        FilterOption("gender", "Хүйс", GENDER),
        FilterOption("study_type", "Суралцаж буй хэлбэр", STUDY_TYPE),
        FilterOption("recommend_company", "Дахин дадлага хийх санал", RECOMMEND),
        FilterOption("received_salary", "Цалин хөлс авсан уу", YES_NO),
        FilterOption("job_offer_received", "Ажлын байрны санал", YES_NO),
    ),
    search_fields=("major", "company_name", "job_offer_details"),
    list_columns=(
        ("timestamp", "Огноо"),
        ("major", "Мэргэжил"),
        ("company_name", "Дадлага хийсэн байгууллага"),
        ("study_type", "Суралцаж буй хэлбэр"),
        ("recommend_company", "Санал болгох эсэх"),
    ),
    name_field="major",
    distribution_fields=(
        ("recommend_company", "Дахин дадлага хийх санал"),
        ("received_salary", "Цалин хөлс авсан уу"),
        ("job_offer_received", "Ажлын байрны санал авсан уу"),
        ("study_type", "Суралцаж буй хэлбэр"),
        ("gender", "Хүйс"),
    ),
)

SURVEYS = {"employer": EMPLOYER, "student": STUDENT}

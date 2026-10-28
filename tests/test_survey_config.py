"""The rules for admin-edited questions (pure logic, no Flask / database)."""
import copy

import pytest

from app.questions import EMPLOYER, STUDENT
from app.services import survey_config as sc
from app.services.survey_config import ConfigError, InfoField

INFO = {
    "company_name": InfoField("company_name", "1.1. Байгууллагын нэр", None, 200),
    "aimag_city": InfoField("aimag_city", "1.7. Байршил", ("Өвөрхангай", "Төв", "Бусад"), 100),
    "rehire_interest": InfoField("rehire_interest", "2.2. Дахин авах уу?", ("Тийм", "Үгүй", "Магадгүй"), 50),
}


def fields(spec):
    return [q.field for q in spec.rating_questions]


def only_group_key(spec):
    return spec.rating_groups[0].key


# ---- resolving -----------------------------------------------------------------------------
def test_no_edits_means_the_defaults_unchanged():
    assert sc.resolve(EMPLOYER, None) is EMPLOYER
    assert sc.resolve(STUDENT, {}) is STUDENT
    assert sc.resolve(STUDENT, "not a dict") == STUDENT       # a damaged row degrades to the defaults


def test_materialised_defaults_resolve_to_the_same_questions():
    doc = {"groups": sc.default_groups(EMPLOYER)}
    assert sc.resolve(EMPLOYER, doc).rating_groups == EMPLOYER.rating_groups


def test_garbage_in_a_stored_document_is_dropped_not_trusted():
    doc = {
        "title": 5,
        "labels": {"a": 7, "b": "  ok  "},
        "choices": {"c": "not a list", "d": ["x", "X", "", 3, "y"]},
        "groups": [
            "junk",
            {"key": "g", "title": "Group", "questions": [
                {"field": "f1", "label": "One"},
                {"field": "f1", "label": "Duplicate field"},
                {"field": "", "label": "No field"},
                {"field": "f2", "label": ""},
                "junk",
            ]},
            {"key": "g", "title": "Duplicate key"},
            {"key": "h", "title": ""},
        ],
    }
    clean = sc.normalize(doc)
    assert clean["title"] is None
    assert clean["labels"] == {"b": "ok"}
    assert clean["choices"] == {"d": ["x", "y"]}
    assert [g["key"] for g in clean["groups"]] == ["g"]
    assert [q["field"] for q in clean["groups"][0]["questions"]] == ["f1"]
    assert clean["groups"][0]["questions"][0]["short"] == "One"   # missing short falls back to the text
    assert clean["groups"][0]["questions"][0]["active"] is True


# ---- title ---------------------------------------------------------------------------------
def test_title_can_be_changed_and_changing_it_back_removes_the_override():
    doc = sc.set_title({}, EMPLOYER, "  Шинэ   гарчиг ")
    assert sc.resolve(EMPLOYER, doc).title == "Шинэ гарчиг"
    assert sc.set_title(doc, EMPLOYER, EMPLOYER.title)["title"] is None
    assert sc.resolve(EMPLOYER, sc.set_title(doc, EMPLOYER, EMPLOYER.title)) == EMPLOYER


def test_title_must_not_be_blank_or_huge():
    with pytest.raises(ConfigError):
        sc.set_title({}, EMPLOYER, "   ")
    with pytest.raises(ConfigError):
        sc.set_title({}, EMPLOYER, "x" * (sc.MAX_TITLE + 1))


# ---- questions -----------------------------------------------------------------------------
def test_editing_a_question_changes_only_that_question():
    doc = sc.update_question({}, EMPLOYER, "q2_1_1", "Шинэ асуулт?", "Шинэ")
    spec = sc.resolve(EMPLOYER, doc)
    first = spec.rating_questions[0]
    assert (first.field, first.label, first.short) == ("q2_1_1", "Шинэ асуулт?", "Шинэ")
    assert spec.rating_questions[1:] == EMPLOYER.rating_questions[1:]
    assert fields(spec) == fields(EMPLOYER)


def test_a_blank_short_name_is_taken_from_the_question_text():
    doc = sc.update_question({}, STUDENT, "env_1", "Орчин ямар байсан бэ?", "")
    assert sc.resolve(STUDENT, doc).rating_questions[0].short == "Орчин ямар байсан бэ?"
    long_label = "а" * 200
    doc = sc.update_question({}, STUDENT, "env_1", long_label, "")
    short = sc.resolve(STUDENT, doc).rating_questions[0].short
    assert len(short) <= sc.MAX_SHORT and short.endswith("…")


def test_a_new_question_gets_its_own_key_and_goes_last_in_its_group():
    group = only_group_key(STUDENT)
    doc, first = sc.add_question({}, STUDENT, group, "Шинэ асуулт", "Шинэ")
    doc, second = sc.add_question(doc, STUDENT, group, "Дахин нэг", "")
    assert first != second and first.startswith("x_") and second.startswith("x_")
    spec = sc.resolve(STUDENT, doc)
    assert fields(spec)[-2:] == [first, second]
    assert fields(spec)[:-2] == fields(STUDENT)
    # never collides with a real database column
    assert first not in STUDENT.rating_fields + ("gender", "age", "major")


def test_hiding_a_question_removes_it_and_showing_it_brings_it_back():
    doc, visible = sc.toggle_question({}, EMPLOYER, "q2_1_3")
    assert visible is False
    assert "q2_1_3" not in sc.resolve(EMPLOYER, doc).rating_fields
    doc, visible = sc.toggle_question(doc, EMPLOYER, "q2_1_3")
    assert visible is True
    assert sc.resolve(EMPLOYER, doc).rating_fields == EMPLOYER.rating_fields


def test_moving_questions_up_and_down_and_stopping_at_the_ends():
    doc = sc.move_question({}, EMPLOYER, "q2_1_2", "up")
    assert fields(sc.resolve(EMPLOYER, doc))[:3] == ["q2_1_2", "q2_1_1", "q2_1_3"]
    doc = sc.move_question(doc, EMPLOYER, "q2_1_2", "down")
    assert fields(sc.resolve(EMPLOYER, doc)) == fields(EMPLOYER)
    first = sc.move_question({}, EMPLOYER, "q2_1_1", "up")      # already first: nothing happens
    assert fields(sc.resolve(EMPLOYER, first)) == fields(EMPLOYER)
    with pytest.raises(ConfigError):
        sc.move_question({}, EMPLOYER, "q2_1_1", "sideways")


def test_unknown_question_or_group_is_rejected():
    with pytest.raises(ConfigError):
        sc.update_question({}, EMPLOYER, "nope", "x", "x")
    with pytest.raises(ConfigError):
        sc.toggle_question({}, EMPLOYER, "nope")
    with pytest.raises(ConfigError):
        sc.add_question({}, EMPLOYER, "nope", "x")
    with pytest.raises(ConfigError):
        sc.update_group({}, EMPLOYER, "nope", "x")


def test_question_text_is_required_and_limited():
    group = only_group_key(EMPLOYER)
    with pytest.raises(ConfigError):
        sc.add_question({}, EMPLOYER, group, "   ")
    with pytest.raises(ConfigError):
        sc.add_question({}, EMPLOYER, group, "x" * (sc.MAX_LABEL + 1))
    with pytest.raises(ConfigError):
        sc.add_question({}, EMPLOYER, group, "ok", "y" * (sc.MAX_SHORT + 1))


def test_there_is_a_ceiling_on_the_number_of_questions():
    doc, group = {}, only_group_key(STUDENT)
    for i in range(sc.MAX_QUESTIONS - len(STUDENT.rating_fields)):
        doc, _ = sc.add_question(doc, STUDENT, group, f"Асуулт {i}")
    with pytest.raises(ConfigError):
        sc.add_question(doc, STUDENT, group, "Нэг илүү")


# ---- groups --------------------------------------------------------------------------------
def test_new_group_with_questions_and_empty_or_hidden_groups_are_not_shown():
    doc, key = sc.add_group({}, STUDENT, "Шинэ бүлэг", "1 – муу, 5 – сайн")
    assert len(sc.resolve(STUDENT, doc).rating_groups) == 1          # empty group is not shown
    doc, field = sc.add_question(doc, STUDENT, key, "Асуулт")
    groups = sc.resolve(STUDENT, doc).rating_groups
    assert [g.title for g in groups][-1] == "Шинэ бүлэг" and groups[-1].hint == "1 – муу, 5 – сайн"
    assert [q.field for q in groups[-1].questions] == [field]
    doc, visible = sc.toggle_group(doc, STUDENT, key)
    assert visible is False and len(sc.resolve(STUDENT, doc).rating_groups) == 1


def test_group_title_hint_and_order_can_change():
    doc, key = sc.add_group({}, STUDENT, "Хоёр", "")
    doc, _ = sc.add_question(doc, STUDENT, key, "Q")
    doc = sc.move_group(doc, STUDENT, key, "up")
    assert sc.resolve(STUDENT, doc).rating_groups[0].title == "Хоёр"
    doc = sc.update_group(doc, STUDENT, key, "Нэр солив", "тайлбар")
    first = sc.resolve(STUDENT, doc).rating_groups[0]
    assert (first.title, first.hint) == ("Нэр солив", "тайлбар")
    with pytest.raises(ConfigError):
        sc.update_group(doc, STUDENT, key, "", "")


def test_group_limit():
    doc = {}
    for i in range(sc.MAX_GROUPS - len(STUDENT.rating_groups)):
        doc, _ = sc.add_group(doc, STUDENT, f"Бүлэг {i}")
    with pytest.raises(ConfigError):
        sc.add_group(doc, STUDENT, "Нэг илүү")


# ---- fixed questions: wording and choices --------------------------------------------------
def test_fixed_question_wording_and_choices_are_applied():
    doc = sc.update_info_field({}, EMPLOYER, INFO, "aimag_city", "1.7. Аймаг", "Өвөрхангай\nЭрдэнэт\n\nБусад")
    spec = sc.resolve(EMPLOYER, doc)
    assert dict(spec.field_labels) == {"aimag_city": "1.7. Аймаг"}
    assert dict(spec.choice_overrides)["aimag_city"] == ("Өвөрхангай", "Эрдэнэт", "Бусад")


def test_admin_filter_still_accepts_values_from_old_responses():
    doc = sc.update_info_field({}, EMPLOYER, INFO, "aimag_city", "1.7. Байршил", "Эрдэнэт\nӨвөрхангай")
    option = sc.resolve(EMPLOYER, doc).filter_map["aimag_city"]
    assert option.choices[:2] == ("Эрдэнэт", "Өвөрхангай")
    assert set(EMPLOYER.filter_map["aimag_city"].choices) <= set(option.choices)   # old answers stay filterable


def test_values_equal_to_the_defaults_are_not_stored():
    doc = sc.update_info_field({}, EMPLOYER, INFO, "aimag_city", "1.7. Байршил", "Өвөрхангай\nТөв\nБусад")
    assert doc["labels"] == {} and doc["choices"] == {}
    assert sc.resolve(EMPLOYER, doc).field_labels == ()


def test_the_answer_counted_as_positive_cannot_be_removed():
    with pytest.raises(ConfigError) as error:
        sc.update_info_field({}, EMPLOYER, INFO, "rehire_interest", "x", "Үгүй\nМагадгүй")
    assert "Тийм" in str(error.value)
    # ... but it can be reordered and extended
    doc = sc.update_info_field({}, EMPLOYER, INFO, "rehire_interest", "x", "Магадгүй\nТийм\nҮгүй\nЯгаад")
    assert dict(sc.resolve(EMPLOYER, doc).choice_overrides)["rehire_interest"][1] == "Тийм"


def test_choices_are_validated_against_the_database_column():
    too_long = "ш" * 51                                   # employer rehire_interest is VARCHAR(50)
    with pytest.raises(ConfigError):
        sc.update_info_field({}, EMPLOYER, INFO, "rehire_interest", "x", f"Тийм\n{too_long}")
    with pytest.raises(ConfigError):
        sc.update_info_field({}, EMPLOYER, INFO, "aimag_city", "x", "Төв\nтөв")        # duplicate, any case
    with pytest.raises(ConfigError):
        sc.update_info_field({}, EMPLOYER, INFO, "aimag_city", "x", "  \n ")           # nothing left
    with pytest.raises(ConfigError):
        sc.update_info_field({}, EMPLOYER, INFO, "aimag_city", "x", "\n".join(str(i) for i in range(sc.MAX_CHOICES + 1)))


def test_text_questions_have_a_label_but_no_choices():
    doc = sc.update_info_field({}, EMPLOYER, INFO, "company_name", "1.1. Нэр", "ignored")
    assert doc["labels"] == {"company_name": "1.1. Нэр"} and doc["choices"] == {}


def test_only_known_fixed_questions_can_be_edited():
    with pytest.raises(ConfigError):
        sc.update_info_field({}, EMPLOYER, INFO, "email; DROP TABLE", "x", "")
    with pytest.raises(ConfigError):
        sc.update_info_field({}, EMPLOYER, INFO, "company_name", "  ", "")


# ---- the editor entry point ----------------------------------------------------------------
def test_apply_action_dispatches_and_reports_where_to_scroll_back_to():
    doc, message, anchor = sc.apply_action({}, EMPLOYER, INFO, "update_question",
                                           {"key": "q2_1_1", "label": "Шинэ", "short": "ш"})
    assert anchor == "q-q2_1_1" and message and sc.resolve(EMPLOYER, doc).rating_questions[0].label == "Шинэ"

    doc, _, anchor = sc.apply_action(doc, EMPLOYER, INFO, "add_question",
                                     {"key": only_group_key(EMPLOYER), "label": "Нэмэлт"})
    assert anchor.startswith("q-x_")

    _, _, anchor = sc.apply_action(doc, EMPLOYER, INFO, "title", {"title": "Гарчиг"})
    assert anchor == "title"


def test_apply_action_rejects_unknown_actions_and_missing_values():
    with pytest.raises(ConfigError):
        sc.apply_action({}, EMPLOYER, INFO, "drop_database", {})
    with pytest.raises(ConfigError):
        sc.apply_action({}, EMPLOYER, INFO, "update_question", {"key": "q2_1_1"})   # no text
    with pytest.raises(ConfigError):
        sc.apply_action({}, EMPLOYER, INFO, "move_question", {"key": "q2_1_1", "direction": ["up"]})


def test_edits_never_modify_the_document_they_are_given():
    original = sc.update_question({}, EMPLOYER, "q2_1_1", "A", "a")
    snapshot = copy.deepcopy(original)
    sc.update_question(original, EMPLOYER, "q2_1_1", "B", "b")
    sc.toggle_question(original, EMPLOYER, "q2_1_2")
    sc.add_question(original, EMPLOYER, only_group_key(EMPLOYER), "C")
    assert original == snapshot


# ---- what the editor page shows ------------------------------------------------------------
def test_describe_lists_hidden_questions_and_marks_changed_fixed_questions():
    doc, _ = sc.toggle_question({}, EMPLOYER, "q2_1_1")
    doc = sc.update_info_field(doc, EMPLOYER, INFO, "aimag_city", "Шинэ", "Төв\nБусад")
    view = sc.describe(EMPLOYER, doc, INFO)
    questions = view["groups"][0]["questions"]
    assert len(questions) == 9 and questions[0]["active"] is False
    assert questions[0]["first"] and questions[-1]["last"]
    by_name = {f["name"]: f for f in view["fields"]}
    assert by_name["aimag_city"]["changed"] and by_name["aimag_city"]["choices"] == ["Төв", "Бусад"]
    assert not by_name["company_name"]["changed"] and by_name["company_name"]["has_choices"] is False
    assert by_name["rehire_interest"]["protected"] == ("Тийм",)
    assert view["question_count"] == 9

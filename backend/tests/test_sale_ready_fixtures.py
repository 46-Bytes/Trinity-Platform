"""
The Sale Ready fixtures in files/sale_ready/, generated from the client's Excel
by scripts/build_sale_ready_fixtures.py.

These pin the structure the brief and mockup describe, so a regenerated or
hand-edited fixture that drifts from them fails here before it is seeded.
Counts come from the mockup's own data (210 DD items), plus the four close-out
tasks the brief confirmed (C2), giving 147 task templates.
"""
import json
import pathlib
from collections import Counter

import pytest

from app.services.sale_ready_rules import GAP_HANDLINGS, STAGE_TYPES, TASK_SECTIONS
from app.services.scoring_service import ScoringService

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "files" / "sale_ready"


def load(name):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def stages():
    return load("stages.json")["items"]


@pytest.fixture(scope="module")
def tasks():
    return load("task_templates.json")["items"]


@pytest.fixture(scope="module")
def dd():
    return load("dd_templates.json")["items"]


class TestStages:

    def test_fifteen_stages_in_brief_order(self, stages):
        assert [s["stage_code"] for s in stages] == [
            "DIAG", "APPRAISAL", "PRIORITISE", "WORKSHOP",
            "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8",
            "TRANSITION", "SALE_PLANNER", "CLOSEOUT",
        ]
        assert [s["default_order"] for s in stages] == list(range(1, 16))

    def test_four_phases_eight_modules_three_after(self, stages):
        assert Counter(s["stage_type"] for s in stages) == {"pre_module": 4, "module": 8, "post_module": 3}
        assert {s["stage_type"] for s in stages} <= STAGE_TYPES

    def test_module_codes_join_to_diagnostic_scores(self, stages):
        """Module codes must equal the scoring taxonomy so module_scores rank them with no mapping."""
        modules = [s["stage_code"] for s in stages if s["stage_type"] == "module"]
        assert modules == list(ScoringService.SALE_READY_MODULES)

    def test_module_titles_match_the_diagnostic(self, stages):
        """C3: module names follow the Diagnostic, not the Excel ('Legal, Compliance & Property')."""
        titles = {s["stage_code"]: s["title"] for s in stages if s["stage_type"] == "module"}
        assert titles == dict(ScoringService.SALE_READY_MODULES)

    def test_task_creation_follows_the_brief(self, stages):
        """Phase tasks at engagement creation; module tasks when the advisor starts the module."""
        for s in stages:
            expected = "on_start" if s["stage_type"] == "module" else "on_engagement_create"
            assert s["task_creation"] == expected, s["stage_code"]

    def test_onboarding_is_not_a_stage(self, stages):
        """C1 is open: onboarding tasks are held in unresolved.json, not seeded."""
        assert not any("onboard" in s["stage_code"].lower() for s in stages)


class TestTaskTemplates:

    def test_counts_match_the_mockup(self, tasks):
        assert len(tasks) == 147
        assert Counter(t["section"] for t in tasks) == {"must_do": 109, "optional": 38}

    def test_templates_are_never_client_specific(self, tasks):
        assert {t["section"] for t in tasks} <= TASK_SECTIONS - {"client_specific"}

    def test_keys_unique_per_stage(self, tasks):
        keys = [(t["stage_code"], t["template_key"]) for t in tasks]
        assert len(keys) == len(set(keys))

    def test_only_stages_with_authored_tasks_have_templates(self, tasks):
        """The Excel's twelve, plus CLOSEOUT from the mockup (C2). Transition and Sale Planner have none."""
        with_tasks = {t["stage_code"] for t in tasks}
        assert with_tasks == {"DIAG", "APPRAISAL", "PRIORITISE", "WORKSHOP",
                              "M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "CLOSEOUT"}

    def test_closeout_has_the_four_must_do_tasks(self, tasks):
        """C2: the Excel has none; the brief makes the mockup's four the spec."""
        closeout = [t for t in tasks if t["stage_code"] == "CLOSEOUT"]
        assert [t["template_key"] for t in closeout] == [f"CLOSEOUT-MUST-0{i}" for i in range(1, 5)]
        assert {t["section"] for t in closeout} == {"must_do"}
        assert {t["group_title"] for t in closeout} == {"Close-out"}
        assert closeout[0]["title"] == "Review the final position against the original appraisal"

    def test_phases_have_only_must_do(self, tasks):
        phase_sections = {t["section"] for t in tasks if t["stage_code"] in {"DIAG", "APPRAISAL", "PRIORITISE", "WORKSHOP"}}
        assert phase_sections == {"must_do"}

    @pytest.mark.parametrize("stage,must_do,optional", [
        ("M1", 10, 3), ("M2", 10, 4), ("M3", 9, 4), ("M4", 10, 6),
        ("M5", 11, 6), ("M6", 9, 5), ("M7", 13, 5), ("M8", 8, 5),
    ])
    def test_module_task_counts(self, tasks, stage, must_do, optional):
        counts = Counter(t["section"] for t in tasks if t["stage_code"] == stage)
        assert (counts["must_do"], counts["optional"]) == (must_do, optional)


class TestDDTemplates:

    def test_210_items_in_16_categories_and_73_sub_items(self, dd):
        assert len(dd) == 210
        assert len({i["category_code"] for i in dd}) == 16
        assert len({i["sub_item_code"] for i in dd}) == 73

    def test_unique_keys(self, dd):
        assert len({i["item_key"] for i in dd}) == 210

    def test_items_per_stage(self, dd):
        assert Counter(i["stage_code"] for i in dd) == {
            "APPRAISAL": 8, "M1": 21, "M2": 74, "M3": 25, "M4": 14,
            "M5": 18, "M6": 11, "M7": 14, "M8": 15, "TRANSITION": 10,
        }

    def test_every_sub_item_belongs_to_one_stage(self, dd):
        """One Drive folder per sub-item must map to exactly one stage's register."""
        stages_by_sub = {}
        for item in dd:
            stages_by_sub.setdefault(item["sub_item_code"], set()).add(item["stage_code"])
        assert all(len(s) == 1 for s in stages_by_sub.values())

    def test_codes_are_consistent(self, dd):
        for item in dd:
            assert item["sub_item_code"].split(".")[0] == item["category_code"], item["item_key"]

    def test_every_item_has_a_document(self, dd):
        assert all(i["document"] for i in dd)


class TestSalePlannerAndTemplates:

    def test_sale_planner_lists(self):
        config = load("sale_planner.json")["config"]
        assert {k: len(v) for k, v in config.items()} == {
            "sale_types": 2, "sale_structures": 5, "value_proposition_structures": 5,
            "marketing_questions": 10, "issues": 43,
        }
        assert [s["label"] for s in config["sale_types"]] == ["Asset Sale", "Share Sale"]

    def test_templates_library(self):
        items = load("templates.json")["items"]
        assert len(items) == 24
        assert len({i["template_key"] for i in items}) == 24

    def test_unresolved_items_are_recorded(self):
        """Content waiting on the client is kept, keyed by its question, not dropped."""
        unresolved = load("unresolved.json")["items"]
        assert len(unresolved["C1_onboarding_tasks"]["tasks"]) == 7

    def test_resolved_items_record_what_was_decided(self):
        """C2 and C3 are answered; the note keeps why, and what the client's own files say."""
        unresolved = load("unresolved.json")["items"]
        assert unresolved["C3_m2_title"]["seeded_stage_title"] == ScoringService.SALE_READY_MODULES["M2"]
        assert unresolved["C3_m2_title"]["excel_and_brief_title"] == "Legal, Compliance, Property & Assets"
        assert len(unresolved["C2_closeout_tasks"]["tasks"]) == 4


def test_gap_vocabulary_matches_the_brief():
    """Fix in Sale Ready, disclose as is, or refer to Value Builder."""
    assert GAP_HANDLINGS == {"fix", "disclose", "refer"}

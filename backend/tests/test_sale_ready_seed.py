"""
scripts/seed_sale_ready_program.py

Validation tests are pure. The seeding tests run inside the rollback-only
db_session from conftest, so nothing they write survives. Counts are asserted
as "active rows equal the fixture" rather than "N created", so the tests pass
whether or not the local database has been seeded already.
"""
import copy
import json

import pytest

from app.models.sale_ready import ProgramDDTemplate, ProgramStage, ProgramTaskTemplate
from scripts.seed_sale_ready_program import (
    FixtureError,
    load_fixtures,
    seed_from_fixtures,
    validate_fixtures,
    value_builder_fingerprint,
)

TABLES = {"stages": ProgramStage, "task_templates": ProgramTaskTemplate, "dd_templates": ProgramDDTemplate}


@pytest.fixture(scope="module")
def fixtures():
    return load_fixtures()


def write_fixtures(directory, data):
    """Write a (possibly edited) copy of the fixtures, in the same file shapes."""
    files = {
        "stages.json": {"items": data["stages"]},
        "task_templates.json": {"items": data["tasks"]},
        "dd_templates.json": {"items": data["dd"]},
        "sale_planner.json": {"config": data["sale_planner"]},
    }
    for name, payload in files.items():
        (directory / name).write_text(json.dumps(payload), encoding="utf-8")
    return str(directory)


def active_count(db, model):
    return db.query(model).filter(model.program_type == "sale_ready", model.is_active == True).count()  # noqa: E712


# ----------------------------------------------------------------------
# Validation (pure)
# ----------------------------------------------------------------------
class TestValidation:

    def test_shipped_fixtures_are_valid(self, fixtures):
        validate_fixtures(fixtures)

    def _broken(self, fixtures, mutate):
        data = copy.deepcopy(fixtures)
        mutate(data)
        with pytest.raises(FixtureError) as exc:
            validate_fixtures(data)
        return str(exc.value)

    def test_task_on_unknown_stage(self, fixtures):
        msg = self._broken(fixtures, lambda d: d["tasks"][0].update(stage_code="NOPE"))
        assert "unknown stage_code" in msg

    def test_client_specific_template_refused(self, fixtures):
        msg = self._broken(fixtures, lambda d: d["tasks"][0].update(section="client_specific"))
        assert "section" in msg

    def test_duplicate_dd_key(self, fixtures):
        msg = self._broken(fixtures, lambda d: d["dd"][1].update(item_key=d["dd"][0]["item_key"]))
        assert "duplicate item_key" in msg

    def test_other_program_type_refused(self, fixtures):
        """The seed is Sale Ready only; a Value Builder row in the fixtures is an error."""
        msg = self._broken(fixtures, lambda d: d["dd"][0].update(program_type="value_builder"))
        assert "program_type must be 'sale_ready'" in msg

    def test_module_codes_must_match_scoring_taxonomy(self, fixtures):
        def rename(d):
            next(s for s in d["stages"] if s["stage_code"] == "M2").update(stage_code="M_LEGAL")
        assert "module stage codes" in self._broken(fixtures, rename)

    def test_title_longer_than_column(self, fixtures):
        msg = self._broken(fixtures, lambda d: d["tasks"][0].update(title="x" * 256))
        assert "column allows 255" in msg

    def test_every_problem_is_reported_at_once(self, fixtures):
        def two(d):
            d["tasks"][0]["stage_code"] = "NOPE"
            d["dd"][0]["program_type"] = "value_builder"
        msg = self._broken(fixtures, two)
        assert msg.startswith("2 problem(s)") or msg.startswith("3 problem(s)")


# ----------------------------------------------------------------------
# Seeding (rolled back)
# ----------------------------------------------------------------------
class TestSeed:

    def test_active_rows_match_the_fixtures(self, db_session, fixtures):
        result = seed_from_fixtures(db=db_session)
        for name, model in TABLES.items():
            t = result[name]
            expected = result["fixture_counts"][name]
            assert t["created"] + t["updated"] + t["unchanged"] + t["reactivated"] == expected
            assert active_count(db_session, model) == expected
        assert result["fixture_counts"] == {"stages": 15, "task_templates": 147, "dd_templates": 210}

    def test_reseed_is_a_no_op(self, db_session):
        seed_from_fixtures(db=db_session)
        second = seed_from_fixtures(db=db_session)
        for name in TABLES:
            t = second[name]
            assert (t["created"], t["updated"], t["reactivated"], t["retired"]) == (0, 0, 0, 0), name

    def test_ids_survive_a_reseed(self, db_session):
        seed_from_fixtures(db=db_session)
        before = {r.item_key: r.id for r in db_session.query(ProgramDDTemplate).filter_by(program_type="sale_ready")}
        seed_from_fixtures(db=db_session)
        after = {r.item_key: r.id for r in db_session.query(ProgramDDTemplate).filter_by(program_type="sale_ready")}
        assert before == after

    def test_dropped_row_is_retired_then_reactivated(self, db_session, fixtures, tmp_path):
        seed_from_fixtures(db=db_session)
        dropped_key = fixtures["dd"][-1]["item_key"]
        row_id = db_session.query(ProgramDDTemplate).filter_by(item_key=dropped_key).one().id

        without = copy.deepcopy(fixtures)
        without["dd"] = without["dd"][:-1]
        retired = seed_from_fixtures(write_fixtures(tmp_path, without), db=db_session)
        assert retired["dd_templates"]["retired"] == 1
        row = db_session.query(ProgramDDTemplate).filter_by(item_key=dropped_key).one()
        assert row.is_active is False and row.id == row_id  # retired, not deleted

        restored = seed_from_fixtures(db=db_session)
        assert restored["dd_templates"]["reactivated"] == 1
        assert db_session.query(ProgramDDTemplate).filter_by(item_key=dropped_key).one().id == row_id

    def test_dry_run_writes_nothing(self, db_session):
        before = {name: db_session.query(model).filter_by(program_type="sale_ready").count()
                  for name, model in TABLES.items()}
        seed_from_fixtures(db=db_session, dry_run=True)
        after = {name: db_session.query(model).filter_by(program_type="sale_ready").count()
                 for name, model in TABLES.items()}
        assert before == after

    def test_value_builder_rows_untouched(self, db_session):
        before = value_builder_fingerprint(db_session)
        seed_from_fixtures(db=db_session)
        assert value_builder_fingerprint(db_session) == before

    def test_content_is_loaded_verbatim(self, db_session, fixtures):
        seed_from_fixtures(db=db_session)
        item = fixtures["dd"][0]
        row = db_session.query(ProgramDDTemplate).filter_by(item_key=item["item_key"]).one()
        assert (row.document_required, row.action_step, row.stage_code, row.sub_item_code) == (
            item["document"], item["action_step"], item["stage_code"], item["sub_item_code"])

        task = fixtures["tasks"][0]
        trow = db_session.query(ProgramTaskTemplate).filter_by(
            stage_code=task["stage_code"], template_key=task["template_key"]).one()
        assert (trow.title, trow.section, trow.group_title) == (task["title"], task["section"], task["group_title"])

    def test_sale_planner_lists_are_the_stage_config(self, db_session, fixtures):
        seed_from_fixtures(db=db_session)
        stage = db_session.query(ProgramStage).filter_by(program_type="sale_ready", stage_code="SALE_PLANNER").one()
        assert stage.ui_config == fixtures["sale_planner"]
        others = db_session.query(ProgramStage).filter(
            ProgramStage.program_type == "sale_ready", ProgramStage.stage_code != "SALE_PLANNER")
        assert all(s.ui_config is None for s in others)

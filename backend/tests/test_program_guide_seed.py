"""
Tests for the module card library seed script.

The script is the only write path to program_module_deliverable, which is the
table the whole status engine reads. Two behaviours matter more than the rest
and are the reason this file exists:

  - an edit must update the row IN PLACE, because live
    EngagementModuleDeliverable rows hold its id as a foreign key;
  - a deliverable dropped from the fixture must be RETIRED, not deleted,
    because that foreign key cascades and deleting would take every
    engagement's completion history with it.

Each test seeds under its own generated program_type, so nothing here depends
on - or disturbs - whatever value_builder content the target database already
holds.

Run with: pytest tests/test_program_guide_seed.py -v
"""
import json
import uuid

import pytest

from app.models.program_deliverable import EngagementModuleDeliverable, ProgramModuleDeliverable
from app.models.program_guide import ProgramModuleContent
from app.schemas.program_guide import ProgramModuleContentItem
from app.services.program_guide_service import ProgramGuideService
from app.services.scoring_service import ScoringService
from scripts.seed_program_guide_content import (
    DEFAULT_FIXTURE,
    FixtureError,
    seed_from_file,
    validate_fixture,
)


@pytest.fixture
def program_type():
    """A program_type nothing else in the database uses."""
    return f"test_program_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def write_fixture(tmp_path, program_type):
    """Write a fixture file and return its path."""
    counter = {"n": 0}

    def _write(modules):
        counter["n"] += 1
        path = tmp_path / f"fixture_{counter['n']}.json"
        for entry in modules:
            entry.setdefault("program_type", program_type)
            entry.setdefault("display_order", 1)
            entry.setdefault("title", "Test Module")
        path.write_text(json.dumps(modules), encoding="utf-8")
        return str(path)

    return _write


def _module(code="V1", deliverables=None, **extra):
    entry = {"module_code": code, "deliverables": deliverables if deliverables is not None else []}
    entry.update(extra)
    return entry


def _deliverable(key, title="A deliverable", is_mandatory=True, **extra):
    item = {"key": key, "title": title, "is_mandatory": is_mandatory}
    item.update(extra)
    return item


def _presets(db, program_type, module_code="V1"):
    return (
        db.query(ProgramModuleDeliverable)
        .filter(
            ProgramModuleDeliverable.program_type == program_type,
            ProgramModuleDeliverable.module_code == module_code,
        )
        .order_by(ProgramModuleDeliverable.display_order)
        .all()
    )


def _card(db, program_type, module_code="V1"):
    return (
        db.query(ProgramModuleContent)
        .filter(
            ProgramModuleContent.program_type == program_type,
            ProgramModuleContent.module_code == module_code,
        )
        .one()
    )


# ----------------------------------------------------------------------
# Idempotency
# ----------------------------------------------------------------------
class TestIdempotency:

    def test_seeding_twice_creates_nothing_the_second_time(self, db_session, write_fixture, program_type):
        path = write_fixture([_module(deliverables=[_deliverable("V1-D1"), _deliverable("V1-D2")])])

        first = seed_from_file(path, db=db_session)
        second = seed_from_file(path, db=db_session)

        assert first["cards"]["created"] == 1
        assert first["deliverables"]["created"] == 2
        assert second["cards"]["created"] == 0
        assert second["deliverables"]["created"] == 0
        assert second["deliverables"]["updated"] == 2
        assert len(_presets(db_session, program_type)) == 2

    def test_display_order_follows_array_position(self, db_session, write_fixture, program_type):
        path = write_fixture([_module(deliverables=[
            _deliverable("V1-D1", title="First"),
            _deliverable("V1-D2", title="Second"),
            _deliverable("V1-D3", title="Third"),
        ])])
        seed_from_file(path, db=db_session)

        rows = _presets(db_session, program_type)
        assert [r.display_order for r in rows] == [1, 2, 3]
        assert [r.title for r in rows] == ["First", "Second", "Third"]

    def test_reordering_the_array_reorders_the_presets(self, db_session, write_fixture, program_type):
        seed_from_file(write_fixture([_module(deliverables=[
            _deliverable("V1-D1", title="First"),
            _deliverable("V1-D2", title="Second"),
        ])]), db=db_session)

        seed_from_file(write_fixture([_module(deliverables=[
            _deliverable("V1-D2", title="Second"),
            _deliverable("V1-D1", title="First"),
        ])]), db=db_session)

        rows = _presets(db_session, program_type)
        assert [r.deliverable_key for r in rows] == ["V1-D2", "V1-D1"]


# ----------------------------------------------------------------------
# In-place updates - the foreign key must survive
# ----------------------------------------------------------------------
class TestUpdatesInPlace:

    def test_editing_a_deliverable_preserves_its_id(self, db_session, write_fixture, program_type):
        """
        The id is a foreign key from every engagement's instance row. Replacing
        the row to apply an edit would orphan all of them.
        """
        seed_from_file(write_fixture([_module(deliverables=[
            _deliverable("V1-D1", title="Original", is_mandatory=True),
        ])]), db=db_session)
        original_id = _presets(db_session, program_type)[0].id

        seed_from_file(write_fixture([_module(deliverables=[
            _deliverable("V1-D1", title="Renamed", is_mandatory=False),
        ])]), db=db_session)

        rows = _presets(db_session, program_type)
        assert len(rows) == 1
        assert rows[0].id == original_id
        assert rows[0].title == "Renamed"
        assert rows[0].is_mandatory is False

    def test_edits_reach_live_engagements(self, db_session, write_fixture, program_type, test_engagement):
        """Live-reference, not snapshot: the instance holds no copy of the title."""
        seed_from_file(write_fixture([_module(deliverables=[
            _deliverable("V1-D1", title="Original"),
        ])]), db=db_session)
        preset = _presets(db_session, program_type)[0]

        instance = EngagementModuleDeliverable(
            engagement_id=test_engagement.id,
            module_code="V1",
            library_deliverable_id=preset.id,
            is_complete=True,
        )
        db_session.add(instance)
        db_session.flush()

        seed_from_file(write_fixture([_module(deliverables=[
            _deliverable("V1-D1", title="Renamed"),
        ])]), db=db_session)

        db_session.refresh(instance)
        assert instance.library_deliverable_id == preset.id
        assert instance.is_complete is True
        assert _presets(db_session, program_type)[0].title == "Renamed"


# ----------------------------------------------------------------------
# Retirement, never deletion
# ----------------------------------------------------------------------
class TestRetirement:

    def test_a_dropped_key_is_retired_not_deleted(self, db_session, write_fixture, program_type):
        seed_from_file(write_fixture([_module(deliverables=[
            _deliverable("V1-D1"), _deliverable("V1-D2"),
        ])]), db=db_session)

        result = seed_from_file(write_fixture([_module(deliverables=[
            _deliverable("V1-D1"),
        ])]), db=db_session)

        rows = _presets(db_session, program_type)
        assert len(rows) == 2, "the dropped preset must still exist"
        assert result["deliverables"]["retired"] == 1
        assert {r.deliverable_key: r.is_active for r in rows} == {"V1-D1": True, "V1-D2": False}

    def test_retiring_preserves_engagement_completion_history(
        self, db_session, write_fixture, program_type, test_engagement
    ):
        """
        The whole reason retirement exists. library_deliverable_id cascades on
        delete, so a DELETE here would silently destroy this row.
        """
        seed_from_file(write_fixture([_module(deliverables=[_deliverable("V1-D1")])]), db=db_session)
        preset = _presets(db_session, program_type)[0]

        instance = EngagementModuleDeliverable(
            engagement_id=test_engagement.id,
            module_code="V1",
            library_deliverable_id=preset.id,
            is_complete=True,
        )
        db_session.add(instance)
        db_session.flush()
        instance_id = instance.id

        seed_from_file(write_fixture([_module(deliverables=[])]), db=db_session)

        survivor = (
            db_session.query(EngagementModuleDeliverable)
            .filter(EngagementModuleDeliverable.id == instance_id)
            .one_or_none()
        )
        assert survivor is not None, "completion history was destroyed by a cascade"
        assert survivor.is_complete is True

    def test_a_returning_key_is_reactivated(self, db_session, write_fixture, program_type):
        seed_from_file(write_fixture([_module(deliverables=[_deliverable("V1-D1")])]), db=db_session)
        original_id = _presets(db_session, program_type)[0].id

        seed_from_file(write_fixture([_module(deliverables=[])]), db=db_session)
        assert _presets(db_session, program_type)[0].is_active is False

        result = seed_from_file(write_fixture([_module(deliverables=[_deliverable("V1-D1")])]), db=db_session)

        row = _presets(db_session, program_type)[0]
        assert row.is_active is True
        assert row.id == original_id, "reactivation must not mint a new row"
        assert result["deliverables"]["reactivated"] == 1

    def test_retiring_is_scoped_to_its_own_module(self, db_session, write_fixture, program_type):
        """A module's absent keys must not retire another module's presets."""
        seed_from_file(write_fixture([
            _module("V1", deliverables=[_deliverable("V1-D1")]),
            _module("V2", deliverables=[_deliverable("V2-D1")]),
        ]), db=db_session)

        seed_from_file(write_fixture([
            _module("V1", deliverables=[]),
            _module("V2", deliverables=[_deliverable("V2-D1")]),
        ]), db=db_session)

        assert _presets(db_session, program_type, "V1")[0].is_active is False
        assert _presets(db_session, program_type, "V2")[0].is_active is True


# ----------------------------------------------------------------------
# The derived legacy column
# ----------------------------------------------------------------------
class TestDerivedLegacyColumn:

    def test_legacy_deliverables_is_a_derived_string_list(self, db_session, write_fixture, program_type):
        """
        ProgramModuleContent.deliverables stays List[str] so ProgramGuideView
        and ModuleCard keep working untouched - it is now derived from the
        preset titles rather than authored.
        """
        seed_from_file(write_fixture([_module(deliverables=[
            _deliverable("V1-D1", title="Financial Health Summary"),
            _deliverable("V1-D2", title="Pricing Review"),
        ])]), db=db_session)

        card = _card(db_session, program_type)
        assert card.deliverables == ["Financial Health Summary", "Pricing Review"]

        # The existing API schema must still validate it unchanged.
        item = ProgramModuleContentItem.model_validate(card)
        assert item.deliverables == ["Financial Health Summary", "Pricing Review"]

    def test_required_inputs_round_trips(self, db_session, write_fixture, program_type):
        inputs = [
            {"key": "V1-I1", "label": "Diagnostic scores", "source": "trinity"},
            {"key": "V1-I2", "label": "Prior module output", "source": "earlier_module",
             "fallback": "Agree provisional priorities in session"},
        ]
        seed_from_file(write_fixture([_module(required_inputs=inputs, deliverables=[])]), db=db_session)

        item = ProgramModuleContentItem.model_validate(_card(db_session, program_type))
        assert item.required_inputs == inputs


# ----------------------------------------------------------------------
# Fixture validation - nothing is written when the fixture is bad
# ----------------------------------------------------------------------
class TestFixtureValidation:

    def test_the_real_fixture_is_valid(self):
        with open(DEFAULT_FIXTURE, "r", encoding="utf-8") as f:
            validate_fixture(json.load(f))

    def test_bare_string_deliverables_are_rejected(self):
        """The pre-S1 fixture shape. Seeding it would key the library on nothing."""
        with pytest.raises(FixtureError, match="expected an object"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": ["PLACEHOLDER: Financial Health Summary"],
            }])

    @pytest.mark.parametrize("item,expected", [
        ({"title": "T", "is_mandatory": True}, "missing 'key'"),
        ({"key": "V1-D1", "is_mandatory": True}, "missing 'title'"),
        ({"key": "V1-D1", "title": "T"}, "'is_mandatory' must be true or false"),
        ({"key": "V1-D1", "title": "T", "is_mandatory": "yes"}, "'is_mandatory' must be true or false"),
    ])
    def test_malformed_deliverables_are_rejected(self, item, expected):
        with pytest.raises(FixtureError, match=expected):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [item],
            }])

    def test_duplicate_keys_within_a_module_are_rejected(self):
        with pytest.raises(FixtureError, match="duplicate deliverable key"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [_deliverable("V1-D1"), _deliverable("V1-D1")],
            }])

    def test_unknown_input_source_is_rejected(self):
        with pytest.raises(FixtureError, match="not in"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "required_inputs": [{"key": "I1", "label": "L", "source": "somewhere_else"}],
                "deliverables": [],
            }])

    def test_validation_runs_before_any_write(self, db_session, write_fixture, program_type):
        """A typo in the last module must not leave the earlier ones seeded."""
        path = write_fixture([
            _module("V1", deliverables=[_deliverable("V1-D1")]),
            _module("V2", deliverables=[{"key": "V2-D1", "title": "No mandatory flag"}]),
        ])
        with pytest.raises(FixtureError):
            seed_from_file(path, db=db_session)

        assert _presets(db_session, program_type, "V1") == []

    def test_every_problem_is_reported_at_once(self):
        with pytest.raises(FixtureError) as exc:
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [{"title": "T"}, {"key": "V1-D2"}],
            }])
        message = str(exc.value)
        assert "missing 'key'" in message
        assert "missing 'title'" in message


# ----------------------------------------------------------------------
# Module rename safety
# ----------------------------------------------------------------------
class TestModuleNameAliases:
    """
    BBA findings store priority_area as freeform text, so rows written before a
    rename still carry the old wording and must keep resolving.
    """

    @pytest.mark.parametrize("old_name,expected_code", [
        ("Brand, IP & Competitive Advantage", "V8"),
        ("People", "V4"),
    ])
    def test_retired_names_still_resolve(self, old_name, expected_code):
        code = ProgramGuideService._match_priority_area_to_module(
            old_name, ScoringService.VALUE_BUILDER_MODULES
        )
        assert code == expected_code

    def test_current_names_resolve(self):
        for code, name in ScoringService.VALUE_BUILDER_MODULES.items():
            resolved = ProgramGuideService._match_priority_area_to_module(
                name, ScoringService.VALUE_BUILDER_MODULES
            )
            assert resolved == code, f"{name} resolved to {resolved}, expected {code}"

    def test_every_alias_points_at_a_live_code(self):
        """A stale alias is worse than none - it silently maps to nothing."""
        for name, code in ProgramGuideService.MODULE_NAME_ALIASES.items():
            assert code in ScoringService.VALUE_BUILDER_MODULES, f"alias {name!r} -> unknown code {code}"

    def test_fixture_titles_match_the_scoring_taxonomy(self):
        """
        The two naming sources that diverged before S1. M0 and M12 are guide-only
        modules and correctly absent from the scoring taxonomy.
        """
        with open(DEFAULT_FIXTURE, "r", encoding="utf-8") as f:
            fixture = json.load(f)

        mismatches = [
            (entry["module_code"], entry["title"], ScoringService.VALUE_BUILDER_MODULES[entry["module_code"]])
            for entry in fixture
            if entry["module_code"] in ScoringService.VALUE_BUILDER_MODULES
            and entry["title"] != ScoringService.VALUE_BUILDER_MODULES[entry["module_code"]]
        ]
        assert mismatches == []

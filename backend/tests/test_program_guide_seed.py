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
    VALID_NOTE_SECTIONS,
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

    def test_every_card_section_round_trips(self, db_session, write_fixture, program_type):
        """
        Each Part B section survives the seed and comes back out through the API
        schema. Checked in one test because the failure mode is a field silently
        dropped from the upsert, which one assertion per section would catch no
        better than all of them together.
        """
        sections = {
            "focus": "Financial clarity and a reporting rhythm.",
            "core_outcomes": ["The owner can explain their financial position."],
            "preparation_summary": {"owner": "Advisor", "duration": "60 to 120 minutes"},
            "sessions": [{
                "key": "V1-S1", "title": "Financial Workshop",
                "duration": "Target 95 to 130 minutes", "format": "In person or online",
                "agenda": [{
                    "key": "V1-S1-A3", "title": "Expenses review", "duration": "20 to 25 minutes",
                    "detail": "Work through the major expense lines.",
                    "questions": ["What has grown fastest, and why?"],
                }],
            }],
            "post_session_actions": {
                "owner": "Advisor", "duration": "45 to 60 minutes",
                "items": ["Finalise the Financial Health Summary."],
            },
            "guardrails": {
                "must_not": ["redo bookkeeping or rebuild the accounts"],
                "note": "These are boundaries of profession, not boundaries of module.",
            },
            "quality_standards": ["Invoicing changes have a named owner."],
        }
        seed_from_file(write_fixture([_module(deliverables=[], **sections)]), db=db_session)

        item = ProgramModuleContentItem.model_validate(_card(db_session, program_type))
        for field, expected in sections.items():
            assert getattr(item, field) == expected, f"{field} did not round-trip"

    def test_a_phase_without_a_duration_is_accepted(self, db_session, write_fixture, program_type):
        """
        The regression Part C exposed. V1 states a duration for every phase and
        V2 states none, so requiring one rejected a valid module while buying
        nothing - no code computes on durations.
        """
        seed_from_file(write_fixture([_module(
            preparation_summary={"owner": "Advisor"},
            between_sessions={"owner": "Advisor", "items": ["Run the plan generator."]},
            post_session_actions={"owner": "Advisor", "items": ["Issue the plan."]},
            deliverables=[],
        )]), db=db_session)

        item = ProgramModuleContentItem.model_validate(_card(db_session, program_type))
        assert item.preparation_summary == {"owner": "Advisor"}
        assert item.between_sessions["items"] == ["Run the plan generator."]

    def test_a_phase_without_an_owner_is_still_rejected(self):
        """Permissive about duration, strict about who does the work."""
        with pytest.raises(FixtureError, match="preparation_summary missing 'owner'"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [], "preparation_summary": {"duration": "1 hour"},
            }])

    def test_section_notes_round_trip(self, db_session, write_fixture, program_type):
        notes = {
            "required_inputs": "Upload is optional but strongly recommended.",
            "deliverables": "The plan template already covers priorities.",
        }
        seed_from_file(write_fixture([_module(section_notes=notes, deliverables=[])]), db=db_session)

        item = ProgramModuleContentItem.model_validate(_card(db_session, program_type))
        assert item.section_notes == notes

    def test_session_note_and_questions_intro_round_trip(self, db_session, write_fixture, program_type):
        """
        questions_intro keeps a lead-in like "For each claimed advantage:"
        attached to the questions it introduces rather than buried in detail.
        """
        sessions = [{
            "key": "V2-S1", "title": "Strategy Workshop",
            "note": "Where two advisors are available, the lead facilitates and whiteboards.",
            "agenda": [{
                "key": "V2-S1-A5", "title": "Competitive position",
                "questions_intro": "For each claimed advantage:",
                "questions": ["Would a customer notice if it disappeared?"],
            }],
        }]
        seed_from_file(write_fixture([_module(sessions=sessions, deliverables=[])]), db=db_session)

        item = ProgramModuleContentItem.model_validate(_card(db_session, program_type))
        assert item.sessions == sessions

    def test_source_note_round_trips(self, db_session, write_fixture, program_type):
        """
        Part C writes "From an earlier module, where available". The source stays
        one of Part A's three literals so it remains filterable; the qualifier is
        preserved beside it rather than dropped.
        """
        inputs = [{
            "key": "V2-I10", "label": "Outputs from any completed module",
            "source": "From an earlier module", "source_note": "where available",
        }]
        seed_from_file(write_fixture([_module(required_inputs=inputs, deliverables=[])]), db=db_session)

        item = ProgramModuleContentItem.model_validate(_card(db_session, program_type))
        assert item.required_inputs == inputs

    def test_tool_build_status_round_trips(self, db_session, write_fixture, program_type):
        """`status` is what lets the UI show an unbuilt tool rather than drop it."""
        tools = [{
            "tool_key": "financial_health_summary",
            "label": "Financial Health Summary generator",
            "when": "pre",
            "status": "To build, Feature 3",
        }]
        seed_from_file(write_fixture([_module(recommended_tools=tools, deliverables=[])]), db=db_session)

        item = ProgramModuleContentItem.model_validate(_card(db_session, program_type))
        assert item.recommended_tools == tools

    def test_deliverable_provenance_round_trips(self, db_session, write_fixture, program_type):
        seed_from_file(write_fixture([
            _module("V1", deliverables=[_deliverable(
                "V1-D1", produced_by="trinity_tool", produced_by_note="advisor-refined", feeds=["V2"],
            )]),
            _module("V2", deliverables=[]),
        ]), db=db_session)

        row = _presets(db_session, program_type)[0]
        assert row.produced_by == "trinity_tool"
        assert row.produced_by_note == "advisor-refined"
        assert row.feeds == ["V2"]

    def test_required_inputs_round_trips(self, db_session, write_fixture, program_type):
        inputs = [
            {"key": "V1-I1", "label": "Diagnostic scores", "source": "Held in Trinity"},
            {"key": "V1-I2", "label": "Prior module output", "source": "From an earlier module",
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

    def test_feeds_naming_an_unknown_module_is_rejected(self):
        """
        The reason the spec's deliverable ids are stable: feeds are real
        cross-references. A typo'd target would otherwise sit in the database
        forever pointing at nothing.
        """
        with pytest.raises(FixtureError, match="feeds unknown module 'V99'"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [_deliverable("V1-D1", feeds=["V99"])],
            }])

    def test_feeds_naming_a_present_module_is_accepted(self):
        validate_fixture([
            {"program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
             "deliverables": [_deliverable("V1-D1", feeds=["V2"])]},
            {"program_type": "p", "module_code": "V2", "display_order": 2, "title": "T", "deliverables": []},
        ])

    def test_unknown_producer_is_rejected(self):
        with pytest.raises(FixtureError, match="produced_by 'wizard' not in"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [_deliverable("V1-D1", produced_by="wizard")],
            }])

    @pytest.mark.parametrize("section,value,expected", [
        ("core_outcomes", "not a list", "core_outcomes must be a list"),
        ("core_outcomes", ["", "ok"], r"core_outcomes\[0\] must be a non-empty string"),
        ("quality_standards", [None], r"quality_standards\[0\] must be a non-empty string"),
        # No "missing duration" case: duration is optional by design, and the
        # owner requirement is pinned in test_a_phase_without_an_owner_is_still_rejected.
        ("post_session_actions", {"owner": "A", "duration": "1h", "items": [""]},
         r"post_session_actions\.items\[0\] must be a non-empty string"),
        ("guardrails", {"note": "n"}, "guardrails missing 'must_not'"),
        ("sessions", [{"title": "No key"}], r"sessions\[0\] missing 'key'"),
        ("sessions", [{"key": "S1"}], r"sessions\[0\] missing 'title'"),
        ("sessions", [{"key": "S1", "title": "T", "agenda": [{"title": "No key"}]}],
         r"agenda\[0\] missing 'key'"),
        ("sessions", [{"key": "S1", "title": "T",
                       "agenda": [{"key": "A1", "title": "T", "questions": [""]}]}],
         r"questions\[0\] must be a non-empty string"),
        ("recommended_tools", [{"label": "No key"}], r"recommended_tools\[0\] missing 'tool_key'"),
    ])
    def test_malformed_card_sections_are_rejected(self, section, value, expected):
        with pytest.raises(FixtureError, match=expected):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [], section: value,
            }])

    def test_unknown_section_note_key_is_rejected(self):
        """
        A typo'd key would store a note nothing ever renders. Silently losing
        authored content is the failure worth guarding against.
        """
        with pytest.raises(FixtureError, match="section_notes key 'delivrables' not in"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [], "section_notes": {"delivrables": "Typo in the key."},
            }])

    def test_empty_section_note_is_rejected(self):
        with pytest.raises(FixtureError, match="section_notes\\['deliverables'\\] must be a non-empty string"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [], "section_notes": {"deliverables": "   "},
            }])

    def test_duplicate_session_and_agenda_keys_are_rejected(self):
        with pytest.raises(FixtureError, match="duplicate agenda key"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [],
                "sessions": [{"key": "S1", "title": "T", "agenda": [
                    {"key": "A1", "title": "One"}, {"key": "A1", "title": "Two"},
                ]}],
            }])

    def test_duplicate_keys_within_a_module_are_rejected(self):
        with pytest.raises(FixtureError, match="duplicate deliverable key"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [_deliverable("V1-D1"), _deliverable("V1-D1")],
            }])

    @pytest.mark.parametrize("source", ["somewhere_else", "trinity", "advisor_upload"])
    def test_unknown_input_source_is_rejected(self, source):
        """
        The slug forms are listed explicitly: they were the pre-Part-A shape and
        would otherwise seed silently, leaving cards rendering a slug.
        """
        with pytest.raises(FixtureError, match="not in"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "required_inputs": [{"key": "I1", "label": "L", "source": source}],
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

    def test_v1_is_transcribed_from_part_b(self):
        """
        V1 is the worked example proving Parts C-L need no code change. If it
        regresses to placeholders, the loader is no longer proven against real
        content.
        """
        with open(DEFAULT_FIXTURE, "r", encoding="utf-8") as f:
            v1 = next(m for m in json.load(f) if m["module_code"] == "V1")

        assert "PLACEHOLDER" not in json.dumps(v1), "V1 still contains placeholder text"

        for section in ("focus", "core_outcomes", "preparation_summary", "sessions",
                        "post_session_actions", "guardrails", "quality_standards"):
            assert v1.get(section), f"V1 is missing {section}"

        keys = [d["key"] for d in v1["deliverables"]]
        assert keys == ["V1-D1", "V1-D2", "V1-D3", "V1-D4", "V1-D5"]

        by_key = {d["key"]: d for d in v1["deliverables"]}
        # The only optional deliverable in the fixture, and the only exercise of
        # the is_mandatory=False path against real content.
        assert by_key["V1-D5"]["is_mandatory"] is False
        assert all(by_key[k]["is_mandatory"] for k in keys if k != "V1-D5")
        assert by_key["V1-D1"]["produced_by"] == "trinity_tool"
        assert by_key["V1-D1"]["feeds"] == ["V2", "V10"]

    def test_v2_is_transcribed_from_part_c(self):
        """
        V2 is the module that proved Parts C-L are not pure data entry: two
        sessions, a between-sessions phase, section notes, a qualified input
        source, and phases with no stated duration.
        """
        with open(DEFAULT_FIXTURE, "r", encoding="utf-8") as f:
            v2 = next(m for m in json.load(f) if m["module_code"] == "V2")

        assert "PLACEHOLDER" not in json.dumps(v2), "V2 still contains placeholder text"

        assert [s["key"] for s in v2["sessions"]] == ["V2-S1", "V2-S2"]
        assert v2["between_sessions"]["owner"] == "Advisor"
        # Part C states an owner but no duration for either phase.
        assert "duration" not in v2["preparation_summary"]
        assert "duration" not in v2["post_session_actions"]
        assert set(v2["section_notes"]) <= VALID_NOTE_SECTIONS

        intro = next(
            a for a in v2["sessions"][0]["agenda"] if a["key"] == "V2-S1-A5"
        )["questions_intro"]
        assert intro == "For each claimed advantage:"

        earlier = next(i for i in v2["required_inputs"] if i["source"] == "From an earlier module")
        assert earlier["source_note"] == "where available"
        assert earlier["fallback"].startswith("V2 does not assume")

        by_key = {d["key"]: d for d in v2["deliverables"]}
        assert list(by_key) == ["V2-D1", "V2-D2", "V2-D3", "V2-D4"]
        # V2-D3 is mandatory per the Playbook, resolving the contradiction Part C
        # flagged against the GPT workflow. Where a client will not use the
        # one-pager the advisor scopes it out on that engagement, which is the
        # reversible choice; optional would have excluded it from completion
        # everywhere.
        assert by_key["V2-D1"]["is_mandatory"] and by_key["V2-D2"]["is_mandatory"]
        assert by_key["V2-D3"]["is_mandatory"]
        assert not by_key["V2-D4"]["is_mandatory"]
        # Part C's Feeds column is "-" for V2-D1: it feeds nothing onward.
        assert "feeds" not in by_key["V2-D1"]
        assert by_key["V2-D2"]["feeds"] == ["V3", "V4", "V10"]

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

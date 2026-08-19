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
                    "questions": [{"items": ["What has grown fastest, and why?"]}],
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

    def test_every_note_combination_round_trips(self, db_session, write_fixture, program_type):
        """
        `title` and `section` are independently optional, and all four
        combinations occur. The titled-AND-section-attached case is the one that
        forced the merge: notes lived in two columns until "Referral to the
        Talent team" arrived, which neither could hold.
        """
        notes = [
            {"key": "both", "section": "guardrails", "title": "Referral to the Talent team",
             "text": "People issues are not out of scope for this module."},
            {"key": "titled-only", "title": "Where the team is very small",
             "text": "Many clients have two or three staff, or none."},
            {"key": "section-only", "section": "deliverables",
             "text": "The plan template already covers priorities."},
            {"key": "neither", "text": "A plain note belonging to nothing in particular."},
        ]
        seed_from_file(write_fixture([_module(notes=notes, deliverables=[])]), db=db_session)

        item = ProgramModuleContentItem.model_validate(_card(db_session, program_type))
        assert item.notes == notes

    def test_agenda_note_round_trips(self, db_session, write_fixture, program_type):
        """
        A trailing instruction after an agenda item's questions. questions_intro
        precedes them; this follows, so it needs its own field.
        """
        sessions = [{
            "key": "V3-S1", "title": "Leadership Alignment Workshop",
            "agenda": [{
                "key": "V3-S1-A3", "title": "Decision rights",
                "questions": [{"items": ["What decisions come to you that should not?"]}],
                "note": "Record simply: decision, decider, threshold, escalates to.",
            }],
        }]
        seed_from_file(write_fixture([_module(sessions=sessions, deliverables=[])]), db=db_session)

        item = ProgramModuleContentItem.model_validate(_card(db_session, program_type))
        assert item.sessions[0]["agenda"][0]["note"].startswith("Record simply:")

    def test_session_note_and_question_groups_round_trip(self, db_session, write_fixture, program_type):
        """
        Questions are groups, labelled or not. The label replaced the old
        questions_intro, which was only ever the label for a single group.
        """
        sessions = [{
            "key": "V5-S1", "title": "Workflow Mapping Workshop",
            "note": "Work one complete workflow at a time.",
            "agenda": [{
                "key": "V5-S1-A3", "title": "Interrogate the map",
                "intro": "Steps 2 to 4 are one workflow. Repeat the sequence.",
                "questions": [
                    {"label": "Pain points", "items": ["Where does this break?"]},
                    {"items": ["Who really does that step?"]},
                ],
            }],
        }]
        seed_from_file(write_fixture([_module(sessions=sessions, deliverables=[])]), db=db_session)

        item = ProgramModuleContentItem.model_validate(_card(db_session, program_type))
        assert item.sessions == sessions

    def test_preparation_checklist_structure_round_trips(self, db_session, write_fixture, program_type):
        checklist = [{
            "key": "send-pre-work-request",
            "title": "Send the pre-work request",
            "text": "Ask the client for three things:",
            "items": ["Which workflows matter most.", "How each currently gets done."],
        }]
        seed_from_file(
            write_fixture([_module(preparation_checklist=checklist, deliverables=[])]), db=db_session
        )

        item = ProgramModuleContentItem.model_validate(_card(db_session, program_type))
        assert item.preparation_checklist == checklist

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
                       "agenda": [{"key": "A1", "title": "T", "questions": [{"items": [""]}]}]}],
         r"items\[0\] must be a non-empty string"),
        ("sessions", [{"key": "S1", "title": "T",
                       "agenda": [{"key": "A1", "title": "T", "questions": [{"label": "Pain points"}]}]}],
         r"questions\[0\] missing 'items'"),
        # The pre-grouping shape: a bare list of strings.
        ("sessions", [{"key": "S1", "title": "T",
                       "agenda": [{"key": "A1", "title": "T", "questions": ["Where does this break?"]}]}],
         r"questions\[0\] must be an object with items"),
        ("recommended_tools", [{"label": "No key"}], r"recommended_tools\[0\] missing 'tool_key'"),
    ])
    def test_malformed_card_sections_are_rejected(self, section, value, expected):
        with pytest.raises(FixtureError, match=expected):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [], section: value,
            }])

    def test_unknown_note_section_is_rejected(self):
        """
        A typo'd section would store a note nothing ever renders. Silently
        losing authored content is the failure worth guarding against.
        """
        with pytest.raises(FixtureError, match="section 'delivrables' not in"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [],
                "notes": [{"key": "k", "section": "delivrables", "text": "Typo in the section."}],
            }])

    @pytest.mark.parametrize("note,expected", [
        ({"text": "X"}, r"notes\[0\] missing 'key'"),
        ({"key": "k"}, r"notes\[0\] missing 'text'"),
        ({"key": "k", "text": "   "}, r"notes\[0\] missing 'text'"),
        ({"key": "k", "text": "X", "title": "  "}, r"notes\[0\] 'title' must be a non-empty string"),
    ])
    def test_malformed_notes_are_rejected(self, note, expected):
        with pytest.raises(FixtureError, match=expected):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [], "notes": [note],
            }])

    def test_a_note_needs_neither_title_nor_section(self):
        """Only `text` is required - the other two are independently optional."""
        validate_fixture([{
            "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
            "deliverables": [], "notes": [{"key": "k", "text": "Just prose."}],
        }])

    def test_duplicate_note_keys_are_rejected(self):
        with pytest.raises(FixtureError, match="duplicate note key"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [], "notes": [
                    {"key": "k", "text": "X"},
                    {"key": "k", "text": "Y"},
                ],
            }])

    @pytest.mark.parametrize("option,expected", [
        ({"term": "Retain", "definition": "d"}, r"options\[0\] missing 'key'"),
        ({"key": "retain", "definition": "d"}, r"options\[0\] missing 'term'"),
        ({"key": "retain", "term": "Retain"}, r"options\[0\] missing 'definition'"),
    ])
    def test_malformed_agenda_options_are_rejected(self, option, expected):
        with pytest.raises(FixtureError, match=expected):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [],
                "sessions": [{"key": "S1", "title": "T", "agenda": [
                    {"key": "A1", "title": "Task review", "options": [option]},
                ]}],
            }])

    def test_duplicate_agenda_option_keys_are_rejected(self):
        with pytest.raises(FixtureError, match="duplicate option key"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [],
                "sessions": [{"key": "S1", "title": "T", "agenda": [
                    {"key": "A1", "title": "Task review", "options": [
                        {"key": "retain", "term": "Retain", "definition": "a"},
                        {"key": "retain", "term": "Repeat", "definition": "b"},
                    ]},
                ]}],
            }])

    def test_duplicate_checklist_keys_are_rejected(self):
        """
        engagement_module_checklist_item.checklist_item_key matches this key, so
        a duplicate silently breaks per-engagement tick-off state.
        """
        with pytest.raises(FixtureError, match="duplicate checklist key"):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [], "preparation_checklist": [
                    {"key": "prep", "text": "One"},
                    {"key": "prep", "text": "Two"},
                ],
            }])

    @pytest.mark.parametrize("item,expected", [
        ({"text": "No key"}, r"preparation_checklist\[0\] missing 'key'"),
        ({"key": "k"}, r"preparation_checklist\[0\] missing 'text'"),
        ({"key": "k", "text": "T", "items": [""]}, r"items\[0\] must be a non-empty string"),
    ])
    def test_malformed_checklist_entries_are_rejected(self, item, expected):
        with pytest.raises(FixtureError, match=expected):
            validate_fixture([{
                "program_type": "p", "module_code": "V1", "display_order": 1, "title": "T",
                "deliverables": [], "preparation_checklist": [item],
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
        assert {n["section"] for n in v2["notes"]} <= VALID_NOTE_SECTIONS

        # Was questions_intro before questions became labelled groups; the intro
        # survived the conversion as the label of V2's single group.
        groups = next(
            a for a in v2["sessions"][0]["agenda"] if a["key"] == "V2-S1-A5"
        )["questions"]
        assert [g.get("label") for g in groups] == ["For each claimed advantage"]

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

    def test_v3_is_transcribed_from_part_d(self):
        """
        V3 introduced the two shapes that had nowhere to live: a titled
        module-level note, and a trailing instruction after an agenda item's
        questions. It is also the first module where every deliverable is
        mandatory.
        """
        with open(DEFAULT_FIXTURE, "r", encoding="utf-8") as f:
            v3 = next(m for m in json.load(f) if m["module_code"] == "V3")

        assert "PLACEHOLDER" not in json.dumps(v3), "V3 still contains placeholder text"

        note = next(n for n in v3["notes"] if n.get("title"))
        assert note["title"] == "Where there is no leadership layer"
        assert "no managers" in note["text"]
        assert "section" not in note, "the leadership-layer note is module-wide, not section-attached"

        decision_rights = next(
            a for a in v3["sessions"][0]["agenda"] if a["key"] == "V3-S1-A3"
        )
        assert decision_rights["note"] == "Record simply: decision, decider, threshold, escalates to."

        keys = [d["key"] for d in v3["deliverables"]]
        assert keys == ["V3-D1", "V3-D2", "V3-D3"]
        assert all(d["is_mandatory"] for d in v3["deliverables"]), "Part D states no optional deliverables"
        assert all(d["produced_by"] == "trinity_tool" for d in v3["deliverables"])

    def test_v4_is_transcribed_from_part_e(self):
        """
        V4 introduced the Retain/Lose/Gain options and the note that is both
        titled and section-attached - the case that merged the two notes fields.
        """
        with open(DEFAULT_FIXTURE, "r", encoding="utf-8") as f:
            v4 = next(m for m in json.load(f) if m["module_code"] == "V4")

        assert "PLACEHOLDER" not in json.dumps(v4), "V4 still contains placeholder text"

        task_review = next(a for a in v4["sessions"][0]["agenda"] if a["key"] == "V4-S1-A4")
        assert [o["term"] for o in task_review["options"]] == ["Retain", "Lose", "Gain"]
        assert task_review["note"].startswith("Record against each role:")

        talent = next(n for n in v4["notes"] if n["key"] == "talent-referral")
        assert talent["title"] == "Referral to the Talent team"
        assert talent["section"] == "guardrails"

        by_key = {d["key"]: d for d in v4["deliverables"]}
        assert list(by_key) == ["V4-D1", "V4-D2", "V4-D3", "V4-D4", "V4-D5"]
        assert not by_key["V4-D5"]["is_mandatory"]
        assert all(by_key[k]["is_mandatory"] for k in by_key if k != "V4-D5")
        # Part E's Feeds column is "-" for D4 and D5.
        assert "feeds" not in by_key["V4-D4"] and "feeds" not in by_key["V4-D5"]
        # The pack generator is the first tool used at two points in a module.
        assert any(t["when"] == "pre, post" for t in v4["recommended_tools"])

    def test_v5_is_transcribed_from_part_f(self):
        """
        V5 introduced labelled question groups, hierarchical preparation and a
        leading agenda intro - and was the first module to need no migration.
        """
        with open(DEFAULT_FIXTURE, "r", encoding="utf-8") as f:
            v5 = next(m for m in json.load(f) if m["module_code"] == "V5")

        assert "PLACEHOLDER" not in json.dumps(v5), "V5 still contains placeholder text"

        interrogate = next(a for a in v5["sessions"][0]["agenda"] if a["key"] == "V5-S1-A3")
        assert [g["label"] for g in interrogate["questions"]] == [
            "Pain points", "Manual handling and duplication", "Owner involvement",
        ]

        validate = next(a for a in v5["sessions"][0]["agenda"] if a["key"] == "V5-S1-A2")
        assert validate["intro"].startswith("Steps 2 to 4 are one workflow")
        # An unlabelled group - the common case, and what V1-V4 converted to.
        assert "label" not in validate["questions"][0]

        pre_work = next(c for c in v5["preparation_checklist"] if c["key"] == "send-pre-work-request")
        assert pre_work["title"] == "Send the pre-work request"
        assert len(pre_work["items"]) == 3

        assert len(v5["notes"]) == 7, "V5 carries the most notes of any module"
        tool_note = next(n for n in v5["notes"] if n["key"] == "tool-carries-expertise")
        assert "not optional to the delivery" in tool_note["text"]

        assert [d["key"] for d in v5["deliverables"]] == ["V5-D1", "V5-D2", "V5-D3", "V5-D4"]
        assert all(d["is_mandatory"] for d in v5["deliverables"])

    def test_v6_is_transcribed_from_part_g(self):
        """
        V6 needed no schema change at all - the first part for which the answer
        was simply to transcribe it. It is also the first module with an agenda
        item carrying questions but no detail.
        """
        with open(DEFAULT_FIXTURE, "r", encoding="utf-8") as f:
            v6 = next(m for m in json.load(f) if m["module_code"] == "V6")

        assert "PLACEHOLDER" not in json.dumps(v6), "V6 still contains placeholder text"

        by_key = {d["key"]: d for d in v6["deliverables"]}
        assert list(by_key) == ["V6-D1", "V6-D2", "V6-D3", "V6-D4", "V6-D5", "V6-D6"]
        assert not by_key["V6-D6"]["is_mandatory"]
        assert all(by_key[k]["is_mandatory"] for k in by_key if k != "V6-D6")
        assert by_key["V6-D3"]["produced_by_note"] == "advisor-selected"

        vendor = next(n for n in v6["notes"] if n["key"] == "vendor-liaison")
        assert vendor["title"] == "Vendor liaison and implementation project management"
        assert vendor["section"] == "guardrails"

        manual_work = next(a for a in v6["sessions"][0]["agenda"] if a["key"] == "V6-S1-A5")
        assert manual_work["questions"], "agenda item 5 carries questions"
        assert "detail" not in manual_work, "and deliberately has no detail - detail is optional"

        v5_input = next(i for i in v6["required_inputs"] if i["key"] == "V6-I2")
        assert "run V5 first" in v5_input["fallback"]
        assert "high level only" in v5_input["fallback"]

    def test_feeds_may_point_backwards(self):
        """
        `feeds` is a dependency graph, not a sequence. V6-D5 feeds V1 and V6-D3
        feeds V5, while V5 feeds V6 - a genuine two-way edge. Pinned here so a
        later "feeds must point forward" assumption fails against real content
        rather than shipping.
        """
        with open(DEFAULT_FIXTURE, "r", encoding="utf-8") as f:
            fixture = json.load(f)

        order = {m["module_code"]: m["display_order"] for m in fixture}
        backward = [
            (m["module_code"], d["key"], target)
            for m in fixture
            for d in m.get("deliverables") or []
            for target in d.get("feeds") or []
            if order[target] < order[m["module_code"]]
        ]
        assert backward, "expected at least one backward feed; V6-D5 feeds V1"

    def test_no_module_still_uses_the_pre_grouping_question_shape(self):
        """Every agenda item's questions are groups, not bare strings."""
        with open(DEFAULT_FIXTURE, "r", encoding="utf-8") as f:
            fixture = json.load(f)

        assert "questions_intro" not in json.dumps(fixture), "questions_intro was absorbed as a label"
        for module in fixture:
            for session in module.get("sessions") or []:
                for item in session.get("agenda") or []:
                    for group in item.get("questions") or []:
                        assert isinstance(group, dict), (
                            f"{item['key']} still uses a flat question list"
                        )

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

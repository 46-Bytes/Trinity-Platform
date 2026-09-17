"""
Contract tests between the seeded module content and what the UI renders it as.

Every rich card section is JSONB, and Pydantic types all of them as
`Dict[str, Any]` - so nothing on the server validates their inner shape, and the
frontend's TypeScript interfaces are hand-written assertions about data no code
checks. That gap is what these tests close: they run over the REAL fixture, so a
content edit that renames `items` to `bullets`, or drops a `key` the render loop
uses, fails here rather than in a client's browser.

The seed script already validates the fixture on write. These are the narrower
question of whether what is stored matches what is drawn.

Run with: pytest tests/test_program_guide_render_contract.py -v
"""
import io
import json
import pathlib

import pytest

FIXTURE = pathlib.Path(__file__).resolve().parents[1] / "files" / "program_guide" / "value_builder_modules.json"

# The three authored source labels. Each maps to its own tag on the card, and an
# unrecognised value falls through to a neutral one - so a typo would not crash
# a card, it would silently mislabel where an input comes from.
INPUT_SOURCES = {"Held in Trinity", "Advisor to upload", "From an earlier module"}

# Sections the card has a place to render a note under. A note carrying anything
# else is stored and never drawn.
RENDERABLE_NOTE_SECTIONS = {
    "core_outcomes",
    "required_inputs",
    "preparation",
    "sessions",
    "between_sessions",
    "recommended_tools",
    "deliverables",
    "post_session_actions",
    "guardrails",
    "quality_standards",
    "business_model_shape",
}

# Tables are drawn under fewer sections than notes are: alongside the card's
# preparation content, alongside its sessions, or - with no section at all - at
# the end of the sessions panel. Anything else has no home.
RENDERABLE_TABLE_SECTIONS = {"business_model_shape", "sessions"}


@pytest.fixture(scope="module")
def modules():
    with io.open(FIXTURE, encoding="utf-8") as handle:
        return json.load(handle)


def _ids(modules):
    return [m["module_code"] for m in modules]


class TestSessionsRenderable:
    """The densest section on the card, and the one with the deepest nesting."""

    def test_every_agenda_item_has_a_key_and_title(self, modules):
        for module in modules:
            for session in module.get("sessions") or []:
                for item in session["agenda"]:
                    assert item.get("key"), f"{module['module_code']} agenda item with no key"
                    assert item.get("title"), f"{item.get('key')} has no title"

    def test_agenda_keys_are_unique_within_a_session(self, modules):
        """They are React list keys; a duplicate silently drops a step."""
        for module in modules:
            for session in module.get("sessions") or []:
                keys = [item["key"] for item in session["agenda"]]
                assert len(keys) == len(set(keys)), f"{session['key']} has duplicate agenda keys"

    def test_session_keys_are_unique_within_a_module(self, modules):
        for module in modules:
            keys = [s["key"] for s in module.get("sessions") or []]
            assert len(keys) == len(set(keys)), f"{module['module_code']} has duplicate session keys"

    def test_question_groups_carry_a_list_of_strings(self, modules):
        """
        The card renders `group.items` directly. A group shaped as a bare list
        of strings - which is what the very first transcription used - would
        render as nothing at all.
        """
        for module in modules:
            for session in module.get("sessions") or []:
                for item in session["agenda"]:
                    for group in item.get("questions") or []:
                        assert isinstance(group, dict), f"{item['key']} question group is not an object"
                        assert isinstance(group.get("items"), list), f"{item['key']} group has no items list"
                        assert group["items"], f"{item['key']} has an empty question group"
                        assert all(isinstance(q, str) for q in group["items"])

    def test_agenda_options_are_term_and_definition(self, modules):
        for module in modules:
            for session in module.get("sessions") or []:
                for item in session["agenda"]:
                    for option in item.get("options") or []:
                        assert option.get("key")
                        assert option.get("term")
                        assert option.get("definition")


class TestRequiredInputsRenderable:

    def test_sources_are_one_of_the_three_authored_labels(self, modules):
        for module in modules:
            for item in module.get("required_inputs") or []:
                assert item["source"] in INPUT_SOURCES, (
                    f"{item['key']} has source {item['source']!r}, which the card has no tag for"
                )

    def test_every_input_has_a_key_and_label(self, modules):
        for module in modules:
            for item in module.get("required_inputs") or []:
                assert item.get("key")
                assert item.get("label")

    def test_input_keys_are_unique_within_a_module(self, modules):
        for module in modules:
            keys = [i["key"] for i in module.get("required_inputs") or []]
            assert len(keys) == len(set(keys)), f"{module['module_code']} has duplicate input keys"

    def test_earlier_module_inputs_state_a_fallback_or_a_note(self, modules):
        """
        Part A: no module may assume another has run, and an input from an
        earlier module needs a stated fallback. The card renders `fallback`
        under the input; `source_note` ("where available") carries the weaker
        form of the same statement.
        """
        for module in modules:
            for item in module.get("required_inputs") or []:
                if item["source"] == "From an earlier module":
                    assert item.get("fallback") or item.get("source_note"), (
                        f"{item['key']} depends on an earlier module but states no fallback"
                    )


class TestNotesAndTablesRenderable:

    def test_note_sections_have_somewhere_to_render(self, modules):
        for module in modules:
            for note in module.get("notes") or []:
                section = note.get("section")
                if section is not None:
                    assert section in RENDERABLE_NOTE_SECTIONS, (
                        f"{note['key']} targets section {section!r}, which the card does not draw"
                    )

    def test_every_note_has_a_key_and_text(self, modules):
        for module in modules:
            for note in module.get("notes") or []:
                assert note.get("key")
                assert note.get("text")

    def test_note_keys_are_unique_within_a_module(self, modules):
        for module in modules:
            keys = [n["key"] for n in module.get("notes") or []]
            assert len(keys) == len(set(keys)), f"{module['module_code']} has duplicate note keys"

    def test_table_cells_do_not_exceed_their_columns(self, modules):
        """
        Cells align to columns by index. A short row is padded when drawn, but a
        long one would put content under no heading at all.
        """
        for module in modules:
            for table in module.get("tables") or []:
                width = len(table["columns"])
                for row in table["rows"]:
                    assert len(row["cells"]) <= width, (
                        f"{table['key']} row {row['key']} has more cells than columns"
                    )

    def test_table_sections_have_somewhere_to_render(self, modules):
        """
        Unlike notes, a table is drawn under one of only a few named sections.
        A matrix targeting any other section would be stored and never shown -
        and an advisor would have no way to tell it was missing.
        """
        for module in modules:
            for table in module.get("tables") or []:
                section = table.get("section")
                if section is not None:
                    assert section in RENDERABLE_TABLE_SECTIONS, (
                        f"{table['key']} targets section {section!r}, which the card does not draw"
                    )

    def test_table_columns_and_rows_carry_keys(self, modules):
        for module in modules:
            for table in module.get("tables") or []:
                assert table.get("key")
                for column in table["columns"]:
                    assert column.get("key") and column.get("label")
                for row in table["rows"]:
                    assert row.get("key") and row.get("label")


class TestToolsRenderable:

    def test_every_tool_has_a_key_and_label(self, modules):
        for module in modules:
            for tool in module["recommended_tools"]:
                assert tool.get("tool_key")
                assert tool.get("label")

    def test_tool_keys_are_unique_within_a_module(self, modules):
        for module in modules:
            keys = [t["tool_key"] for t in module["recommended_tools"]]
            assert len(keys) == len(set(keys)), f"{module['module_code']} has duplicate tool keys"

    def test_an_unbuilt_tool_is_marked_as_such(self, modules):
        """
        The card decides between "Run", "Open" and "Not built yet" from `status`.
        A tool with no launcher and no status would render a dead "No launcher"
        chip, which tells an advisor nothing about whether it is coming.
        """
        launchable = {"bba", "strategy_workbook", "strategic_business_plan", "diagnostic"}
        for module in modules:
            for tool in module["recommended_tools"]:
                if tool["tool_key"] not in launchable:
                    assert tool.get("status"), (
                        f"{tool['tool_key']} has no launcher and no status, so the card cannot label it"
                    )


class TestGuardrailsAndOutcomesRenderable:

    def test_guardrails_carry_a_must_not_list(self, modules):
        for module in modules:
            guardrails = module.get("guardrails")
            if guardrails is None:
                continue
            assert isinstance(guardrails.get("must_not"), list)
            assert guardrails["must_not"], f"{module['module_code']} has an empty must_not"

    def test_guardrails_read_as_a_continuation_of_advisors_must_not(self, modules):
        """
        The card prefixes each entry with "Advisors must not", so an entry that
        already starts with a capital or repeats the prefix reads wrong.
        """
        for module in modules:
            for item in (module.get("guardrails") or {}).get("must_not") or []:
                assert not item.startswith("Advisors"), f"{item!r} duplicates the rendered prefix"
                assert item[0].islower(), f"{item!r} does not continue 'Advisors must not ...'"

    def test_list_sections_hold_strings(self, modules):
        """core_outcomes and quality_standards are rendered as plain bullets."""
        for module in modules:
            for field in ("core_outcomes", "quality_standards"):
                for entry in module.get(field) or []:
                    assert isinstance(entry, str), f"{module['module_code']}.{field} holds a non-string"

    def test_owner_blocks_hold_a_list_of_strings(self, modules):
        for module in modules:
            for field in ("post_session_actions", "between_sessions"):
                block = module.get(field)
                if not block:
                    continue
                assert all(isinstance(item, str) for item in block.get("items") or [])


class TestDeliverablesRenderable:

    def test_deliverable_keys_are_unique_within_a_module(self, modules):
        for module in modules:
            keys = [d["key"] for d in module["deliverables"]]
            assert len(keys) == len(set(keys)), f"{module['module_code']} has duplicate deliverable keys"

    def test_feeds_point_at_real_modules(self, modules):
        """
        `feeds` is a dependency graph, not a sequence - it has backward edges and
        a V5/V6 cycle, both deliberate. What it must not have is an edge to a
        module that does not exist.
        """
        codes = set(_ids(modules))
        for module in modules:
            for deliverable in module["deliverables"]:
                for target in deliverable.get("feeds") or []:
                    assert target in codes, f"{deliverable['key']} feeds unknown module {target!r}"

    def test_every_module_has_at_least_one_mandatory_deliverable(self, modules):
        """
        Module status derives from mandatory deliverables. A module with none
        can only reach Complete through the acted-on guard, which makes its
        progress indicator close to meaningless.
        """
        for module in modules:
            assert any(d["is_mandatory"] for d in module["deliverables"]), (
                f"{module['module_code']} has no mandatory deliverable"
            )

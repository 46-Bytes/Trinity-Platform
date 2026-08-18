"""
Seed/update the module card library from a JSON fixture.

Writes both halves of the library:

  program_module_content       - the card itself (purpose, preparation
                                 checklist, tools, required inputs)
  program_module_deliverable   - the preset deliverables the status engine
                                 derives module status from

Idempotent. Cards upsert on (program_type, module_code); deliverables upsert on
(program_type, module_code, deliverable_key), matching
uq_program_module_deliverable_type_module_key. Re-run this whenever the fixture
changes (e.g. once the client delivers real copy).

Two things worth knowing before editing this:

1. A deliverable that disappears from the fixture is RETIRED (is_active=False),
   never deleted. EngagementModuleDeliverable.library_deliverable_id cascades on
   delete, so removing a preset row would destroy every engagement's completion
   and scope history for it. Retiring hides it from the status query and is
   reversible - putting the key back in the fixture reactivates the same row.

2. Upserts preserve the row id, because live instances hold it as a foreign key.
   Never delete-then-recreate a deliverable to apply an edit.

Usage (from the backend/ directory):
    python scripts/seed_program_guide_content.py
    python scripts/seed_program_guide_content.py --file files/program_guide/value_builder_modules.json
    python scripts/seed_program_guide_content.py --dry-run
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.program_deliverable import ProgramModuleDeliverable
from app.models.program_guide import ProgramModuleContent

DEFAULT_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "files", "program_guide", "value_builder_modules.json",
)

# Part A fixes these as the STORED values, not display labels over some slug -
# its table maps each label to itself. Kept verbatim so what the card renders is
# what the database holds.
VALID_INPUT_SOURCES = {"Held in Trinity", "Advisor to upload", "From an earlier module"}

# The producer half of the spec's "Produced by" column. Only the producer is
# constrained; its qualifier ("advisor-refined") is free text.
VALID_PRODUCERS = {"trinity_tool", "advisor", "client"}

# Sections that may carry a section-level note. Constrained so a typo'd key
# cannot store a note that nothing ever renders - silently losing authored
# content is the failure worth guarding against here.
VALID_NOTE_SECTIONS = {
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
}

# Card sections copied straight through to the row. Listed once so adding a
# section to the fixture means adding it here, not editing two upsert branches.
_PASSTHROUGH_FIELDS = (
    "purpose",
    "focus",
    "core_outcomes",
    "preparation_checklist",
    "preparation_summary",
    "sessions",
    "between_sessions",
    "post_session_actions",
    "guardrails",
    "quality_standards",
    "recommended_tools",
    "required_inputs",
    "notes",
)


class FixtureError(ValueError):
    """The fixture is malformed. Raised before anything is written."""


def _check_text_list(problems, where, field, value) -> None:
    """core_outcomes / quality_standards / guardrails.must_not are plain prose lists."""
    if value is None:
        return
    if not isinstance(value, list):
        problems.append(f"{where}: {field} must be a list of strings")
        return
    for j, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            problems.append(f"{where}: {field}[{j}] must be a non-empty string")


def _check_owner_duration(problems, where, field, value, require_items=False) -> None:
    """
    preparation_summary, between_sessions and post_session_actions share
    {owner, duration, items}.

    `duration` is deliberately NOT required. V1 states one for every phase and
    V2 states none at all, so requiring it rejected a perfectly valid module
    while buying nothing - nothing computes on durations. `owner` stays
    required because a phase with no named owner is a real authoring mistake.
    """
    if value is None:
        return
    if not isinstance(value, dict):
        problems.append(f"{where}: {field} must be an object with an owner")
        return
    if not value.get("owner"):
        problems.append(f"{where}: {field} missing 'owner'")
    if require_items:
        _check_text_list(problems, where, f"{field}.items", value.get("items"))


def _check_options(problems, where, options) -> None:
    """
    A named choice set inside an agenda item, e.g. testing every task against
    Retain / Lose / Gain. Each option is a term and its definition, which is
    neither a question nor prose, so it needs its own shape.
    """
    if options is None:
        return
    if not isinstance(options, list):
        problems.append(f"{where}: options must be a list")
        return

    seen = set()
    for i, option in enumerate(options):
        at = f"{where}: options[{i}]"
        if not isinstance(option, dict):
            problems.append(f"{at} must be an object")
            continue
        key = option.get("key")
        if not key:
            problems.append(f"{at} missing 'key'")
        elif key in seen:
            problems.append(f"{at} duplicate option key {key!r}")
        else:
            seen.add(key)
        for field in ("term", "definition"):
            value = option.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{at} missing '{field}'")


def _check_sessions(problems, where, sessions) -> None:
    if sessions is None:
        return
    if not isinstance(sessions, list):
        problems.append(f"{where}: sessions must be a list")
        return

    seen = set()
    for i, session in enumerate(sessions):
        at = f"{where}: sessions[{i}]"
        if not isinstance(session, dict):
            problems.append(f"{at} must be an object")
            continue
        key = session.get("key")
        if not key:
            problems.append(f"{at} missing 'key'")
        elif key in seen:
            problems.append(f"{at} duplicate session key {key!r}")
        else:
            seen.add(key)
        if not session.get("title"):
            problems.append(f"{at} missing 'title'")

        agenda = session.get("agenda")
        if agenda is None:
            continue
        if not isinstance(agenda, list):
            problems.append(f"{at}.agenda must be a list")
            continue

        seen_agenda = set()
        for j, item in enumerate(agenda):
            spot = f"{at}.agenda[{j}]"
            if not isinstance(item, dict):
                problems.append(f"{spot} must be an object")
                continue
            item_key = item.get("key")
            if not item_key:
                problems.append(f"{spot} missing 'key'")
            elif item_key in seen_agenda:
                problems.append(f"{spot} duplicate agenda key {item_key!r}")
            else:
                seen_agenda.add(item_key)
            if not item.get("title"):
                problems.append(f"{spot} missing 'title'")
            _check_text_list(problems, spot, "questions", item.get("questions"))
            _check_options(problems, spot, item.get("options"))


def _check_notes(problems, where, notes) -> None:
    """
    Prose that is not part of any list.

    `title` and `section` are independently optional, which is the whole point:
    a note may be titled or not, and belong to a named section or to the module
    as a whole. This began as two columns - untitled-by-section and
    titled-module-wide - until a note arrived that was both, and neither held
    it. Only `text` is required.
    """
    if notes is None:
        return
    if not isinstance(notes, list):
        problems.append(f"{where}: notes must be a list")
        return

    seen = set()
    for i, note in enumerate(notes):
        at = f"{where}: notes[{i}]"
        if not isinstance(note, dict):
            problems.append(f"{at} must be an object")
            continue

        key = note.get("key")
        if not key:
            problems.append(f"{at} missing 'key'")
        elif key in seen:
            problems.append(f"{at} duplicate note key {key!r}")
        else:
            seen.add(key)

        text = note.get("text")
        if not isinstance(text, str) or not text.strip():
            problems.append(f"{at} missing 'text'")

        title = note.get("title")
        if title is not None and (not isinstance(title, str) or not title.strip()):
            problems.append(f"{at} 'title' must be a non-empty string when present")

        section = note.get("section")
        if section is not None and section not in VALID_NOTE_SECTIONS:
            problems.append(f"{at} section {section!r} not in {sorted(VALID_NOTE_SECTIONS)}")


def _check_guardrails(problems, where, guardrails) -> None:
    if guardrails is None:
        return
    if not isinstance(guardrails, dict):
        problems.append(f"{where}: guardrails must be an object with must_not and an optional note")
        return
    if not guardrails.get("must_not"):
        problems.append(f"{where}: guardrails missing 'must_not'")
    _check_text_list(problems, where, "guardrails.must_not", guardrails.get("must_not"))


def _check_tools(problems, where, tools) -> None:
    if tools is None:
        return
    if not isinstance(tools, list):
        problems.append(f"{where}: recommended_tools must be a list")
        return
    for j, tool in enumerate(tools):
        if not isinstance(tool, dict):
            problems.append(f"{where}: recommended_tools[{j}] must be an object")
            continue
        for field in ("tool_key", "label"):
            if not tool.get(field):
                problems.append(f"{where}: recommended_tools[{j}] missing '{field}'")


def validate_fixture(modules) -> None:
    """
    Check the whole fixture before writing any of it.

    A typo in module nine should not leave modules one to eight seeded and the
    rest missing, so this runs to completion up front and reports every problem
    at once rather than failing on the first.
    """
    problems = []

    if not isinstance(modules, list) or not modules:
        raise FixtureError("Fixture must be a non-empty list of modules")

    # Collected first so `feeds` can be checked against it below: a deliverable
    # feeding a module that does not exist is a typo, and the whole point of
    # stable ids is that these references resolve.
    known_modules = {e.get("module_code") for e in modules if isinstance(e, dict)}

    seen_modules = set()
    for i, entry in enumerate(modules):
        where = f"entry {i}"
        for field in ("program_type", "module_code", "display_order", "title"):
            if entry.get(field) in (None, ""):
                problems.append(f"{where}: missing required field '{field}'")

        code = entry.get("module_code")
        if code:
            where = f"module {code}"
            key = (entry.get("program_type"), code)
            if key in seen_modules:
                problems.append(f"{where}: duplicate module_code for this program_type")
            seen_modules.add(key)

        for j, item in enumerate(entry.get("required_inputs") or []):
            if not item.get("key"):
                problems.append(f"{where}: required_inputs[{j}] missing 'key'")
            if not item.get("label"):
                problems.append(f"{where}: required_inputs[{j}] missing 'label'")
            source = item.get("source")
            if source not in VALID_INPUT_SOURCES:
                problems.append(
                    f"{where}: required_inputs[{j}] source {source!r} not in {sorted(VALID_INPUT_SOURCES)}"
                )

        _check_text_list(problems, where, "core_outcomes", entry.get("core_outcomes"))
        _check_text_list(problems, where, "quality_standards", entry.get("quality_standards"))
        _check_owner_duration(problems, where, "preparation_summary", entry.get("preparation_summary"))
        _check_owner_duration(
            problems, where, "between_sessions", entry.get("between_sessions"), require_items=True
        )
        _check_owner_duration(
            problems, where, "post_session_actions", entry.get("post_session_actions"), require_items=True
        )
        _check_notes(problems, where, entry.get("notes"))
        _check_sessions(problems, where, entry.get("sessions"))
        _check_guardrails(problems, where, entry.get("guardrails"))
        _check_tools(problems, where, entry.get("recommended_tools"))

        # Deliverables must be objects. The fixture used to hold bare strings;
        # failing loudly here beats seeding a library keyed on nothing.
        seen_keys = set()
        for j, item in enumerate(entry.get("deliverables") or []):
            if not isinstance(item, dict):
                problems.append(
                    f"{where}: deliverables[{j}] is {type(item).__name__}, expected an object "
                    "with key/title/is_mandatory"
                )
                continue
            key = item.get("key")
            if not key:
                problems.append(f"{where}: deliverables[{j}] missing 'key'")
            elif key in seen_keys:
                problems.append(f"{where}: duplicate deliverable key {key!r}")
            else:
                seen_keys.add(key)
            if not item.get("title"):
                problems.append(f"{where}: deliverables[{j}] missing 'title'")
            if not isinstance(item.get("is_mandatory"), bool):
                problems.append(f"{where}: deliverables[{j}] 'is_mandatory' must be true or false")

            producer = item.get("produced_by")
            if producer is not None and producer not in VALID_PRODUCERS:
                problems.append(
                    f"{where}: deliverables[{j}] produced_by {producer!r} not in {sorted(VALID_PRODUCERS)}"
                )

            feeds = item.get("feeds")
            if feeds is not None:
                if not isinstance(feeds, list):
                    problems.append(f"{where}: deliverables[{j}] feeds must be a list of module codes")
                else:
                    for target in feeds:
                        if target not in known_modules:
                            problems.append(
                                f"{where}: deliverables[{j}] feeds unknown module {target!r}"
                            )

    if problems:
        raise FixtureError(
            "Fixture validation failed:\n  " + "\n  ".join(problems)
        )


def _upsert_card(db, entry) -> str:
    """Upsert one program_module_content row. Returns 'created' or 'updated'."""
    # Display-only mirror of the deliverable titles. Derived, never authored:
    # the deliverables the status engine reads live in program_module_deliverable.
    # This keeps ProgramGuideView and ModuleCard working unchanged until the
    # composed view replaces them.
    labels = [d["title"] for d in (entry.get("deliverables") or [])]

    fields = {field: entry.get(field) for field in _PASSTHROUGH_FIELDS}
    fields.update(
        display_order=entry["display_order"],
        title=entry["title"],
        deliverables=labels,
        is_active=entry.get("is_active", True),
    )

    existing = (
        db.query(ProgramModuleContent)
        .filter(
            ProgramModuleContent.program_type == entry["program_type"],
            ProgramModuleContent.module_code == entry["module_code"],
        )
        .first()
    )
    if existing:
        for name, value in fields.items():
            setattr(existing, name, value)
        return "updated"

    db.add(ProgramModuleContent(
        program_type=entry["program_type"],
        module_code=entry["module_code"],
        **fields,
    ))
    return "created"


def _sync_deliverables(db, entry) -> dict:
    """
    Upsert this module's presets and retire any that the fixture dropped.

    Returns a {created, updated, retired, reactivated} tally.
    """
    program_type = entry["program_type"]
    module_code = entry["module_code"]
    fixture_items = entry.get("deliverables") or []

    existing_rows = (
        db.query(ProgramModuleDeliverable)
        .filter(
            ProgramModuleDeliverable.program_type == program_type,
            ProgramModuleDeliverable.module_code == module_code,
        )
        .all()
    )
    by_key = {row.deliverable_key: row for row in existing_rows}

    tally = {"created": 0, "updated": 0, "retired": 0, "reactivated": 0}

    for position, item in enumerate(fixture_items, start=1):
        key = item["key"]
        row = by_key.get(key)

        fields = dict(
            title=item["title"],
            description=item.get("description"),
            is_mandatory=item["is_mandatory"],
            produced_by=item.get("produced_by"),
            produced_by_note=item.get("produced_by_note"),
            feeds=item.get("feeds"),
            # Position in the fixture array IS the order, so reordering the
            # array reorders the card with no renumbering by hand.
            display_order=position,
            is_active=True,
        )

        if row is None:
            db.add(ProgramModuleDeliverable(
                program_type=program_type,
                module_code=module_code,
                deliverable_key=key,
                **fields,
            ))
            tally["created"] += 1
            continue

        # Update in place. The id must survive: live EngagementModuleDeliverable
        # rows hold it as a foreign key, and replacing the row would orphan
        # every engagement's completion state for this deliverable.
        if not row.is_active:
            tally["reactivated"] += 1
        for name, value in fields.items():
            setattr(row, name, value)
        tally["updated"] += 1

    fixture_keys = {item["key"] for item in fixture_items}
    for key, row in by_key.items():
        if key not in fixture_keys and row.is_active:
            # Retire, never delete - see the module docstring.
            row.is_active = False
            tally["retired"] += 1

    return tally


def seed_from_file(fixture_path: str, db=None, dry_run: bool = False) -> dict:
    """
    Seed both library tables from the fixture.

    Pass `db` to run inside an existing session (the test suite does this, so
    the whole seed rolls back); otherwise a session is opened and closed here.
    """
    with open(fixture_path, "r", encoding="utf-8") as f:
        modules = json.load(f)

    validate_fixture(modules)

    owns_session = db is None
    db = db or SessionLocal()
    try:
        cards = {"created": 0, "updated": 0}
        items = {"created": 0, "updated": 0, "retired": 0, "reactivated": 0}

        for entry in modules:
            cards[_upsert_card(db, entry)] += 1
            for key, count in _sync_deliverables(db, entry).items():
                items[key] += count

        if dry_run:
            db.rollback()
        else:
            db.commit()

        return {"modules": len(modules), "cards": cards, "deliverables": items}
    finally:
        if owns_session:
            db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=DEFAULT_FIXTURE, help="Path to the JSON fixture to seed from")
    parser.add_argument("--dry-run", action="store_true", help="Validate and roll back without writing")
    args = parser.parse_args()

    try:
        result = seed_from_file(args.file, dry_run=args.dry_run)
    except FixtureError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    prefix = "DRY RUN - nothing written." if args.dry_run else "Seeded"
    c, d = result["cards"], result["deliverables"]
    print(
        f"{prefix} {args.file}: {result['modules']} modules\n"
        f"  cards:        {c['created']} created, {c['updated']} updated\n"
        f"  deliverables: {d['created']} created, {d['updated']} updated, "
        f"{d['retired']} retired, {d['reactivated']} reactivated"
    )


if __name__ == "__main__":
    main()

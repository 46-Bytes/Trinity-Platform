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


class FixtureError(ValueError):
    """The fixture is malformed. Raised before anything is written."""


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

    existing = (
        db.query(ProgramModuleContent)
        .filter(
            ProgramModuleContent.program_type == entry["program_type"],
            ProgramModuleContent.module_code == entry["module_code"],
        )
        .first()
    )
    if existing:
        existing.display_order = entry["display_order"]
        existing.title = entry["title"]
        existing.purpose = entry.get("purpose")
        existing.preparation_checklist = entry.get("preparation_checklist")
        existing.recommended_tools = entry.get("recommended_tools")
        existing.required_inputs = entry.get("required_inputs")
        existing.deliverables = labels
        existing.is_active = entry.get("is_active", True)
        return "updated"

    db.add(ProgramModuleContent(
        program_type=entry["program_type"],
        module_code=entry["module_code"],
        display_order=entry["display_order"],
        title=entry["title"],
        purpose=entry.get("purpose"),
        preparation_checklist=entry.get("preparation_checklist"),
        recommended_tools=entry.get("recommended_tools"),
        required_inputs=entry.get("required_inputs"),
        deliverables=labels,
        is_active=entry.get("is_active", True),
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

        if row is None:
            db.add(ProgramModuleDeliverable(
                program_type=program_type,
                module_code=module_code,
                deliverable_key=key,
                title=item["title"],
                description=item.get("description"),
                is_mandatory=item["is_mandatory"],
                # Position in the fixture array IS the order, so reordering the
                # array reorders the card with no renumbering by hand.
                display_order=position,
                is_active=True,
            ))
            tally["created"] += 1
            continue

        # Update in place. The id must survive: live EngagementModuleDeliverable
        # rows hold it as a foreign key, and replacing the row would orphan
        # every engagement's completion state for this deliverable.
        if not row.is_active:
            tally["reactivated"] += 1
        row.title = item["title"]
        row.description = item.get("description")
        row.is_mandatory = item["is_mandatory"]
        row.display_order = position
        row.is_active = True
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

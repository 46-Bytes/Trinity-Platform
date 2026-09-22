"""
Seed/update the Sale Ready program templates from files/sale_ready/.

Writes three template tables, all scoped to program_type = 'sale_ready':

  program_stage          stages.json          (+ the Sale Planner lists from
                                                sale_planner.json, stored as that
                                                stage's ui_config)
  program_task_template  task_templates.json
  program_dd_template    dd_templates.json

The fixtures are generated from the client's Excel by
scripts/build_sale_ready_fixtures.py; this script loads them as they are and
never edits their content. It follows seed_program_guide_content.py:

1. The whole fixture set is validated before anything is written, and every
   problem is reported at once.
2. Rows upsert on stable keys - stage_code, (stage_code, template_key),
   item_key - so row ids survive: engagement DD items reference DD templates
   with ON DELETE RESTRICT, and tasks reference task templates.
3. A row missing from the fixtures is RETIRED (is_active = false), never
   deleted; putting it back reactivates the same row.
4. Only 'sale_ready' rows are read or written. Value Builder content lives in
   other tables (program_module_content, program_module_deliverable); a
   fingerprint of those, taken before and after, proves them untouched.

Not seeded here: templates.json (no library table yet) and unresolved.json
(content waiting on client answers).

Usage (from backend/):
    python scripts/seed_sale_ready_program.py --dry-run
    python scripts/seed_sale_ready_program.py
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.program_deliverable import ProgramModuleDeliverable
from app.models.program_guide import ProgramModuleContent
from app.models.sale_ready import (
    ProgramDDTemplate, ProgramGuideContent, ProgramStage, ProgramTaskTemplate,
)
from app.services.program_registry import PROGRAM_SALE_READY
from app.services.sale_ready_rules import (
    SECTION_MUST_DO,
    SECTION_OPTIONAL,
    STAGE_TYPE_MODULE,
    STAGE_TYPES,
)
from app.services.scoring_service import ScoringService

FIXTURE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "files", "sale_ready")

TASK_CREATION_VALUES = {"on_engagement_create", "on_start"}
UI_VARIANTS = {None, "sale_planner", "closeout"}
# Client-specific tasks are added per engagement, so a template is never one.
TEMPLATE_SECTIONS = {SECTION_MUST_DO, SECTION_OPTIONAL}
SALE_PLANNER_KEYS = {"sale_types", "sale_structures", "value_proposition_structures", "marketing_questions", "issues"}


class FixtureError(Exception):
    pass


# ----------------------------------------------------------------------
# Loading and validation
# ----------------------------------------------------------------------
def load_fixtures(fixture_dir: str = FIXTURE_DIR) -> dict:
    def read(name):
        path = os.path.join(fixture_dir, name)
        if not os.path.exists(path):
            raise FixtureError(f"Missing fixture {path}")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    return {
        "stages": read("stages.json")["items"],
        "tasks": read("task_templates.json")["items"],
        "dd": read("dd_templates.json")["items"],
        "sale_planner": read("sale_planner.json")["config"],
        "guide": read("guide.json"),
    }


def _check_length(problems, where, field, value, limit):
    if value is not None and len(str(value)) > limit:
        problems.append(f"{where}: {field} is {len(str(value))} characters, column allows {limit}")


def validate_fixtures(fixtures: dict) -> None:
    """Check every fixture before writing any of it; raise FixtureError listing all problems."""
    problems = []
    stages, tasks, dd, planner = fixtures["stages"], fixtures["tasks"], fixtures["dd"], fixtures["sale_planner"]

    # --- stages ---
    stage_codes, orders = set(), set()
    for i, s in enumerate(stages):
        where = f"stage {s.get('stage_code') or i}"
        for field in ("program_type", "stage_code", "stage_type", "title", "default_order", "task_creation"):
            if s.get(field) in (None, ""):
                problems.append(f"{where}: missing '{field}'")
        if s.get("program_type") != PROGRAM_SALE_READY:
            problems.append(f"{where}: program_type must be '{PROGRAM_SALE_READY}'")
        if s.get("stage_type") not in STAGE_TYPES:
            problems.append(f"{where}: stage_type {s.get('stage_type')!r} not in {sorted(STAGE_TYPES)}")
        if s.get("task_creation") not in TASK_CREATION_VALUES:
            problems.append(f"{where}: task_creation {s.get('task_creation')!r} not in {sorted(TASK_CREATION_VALUES)}")
        if s.get("ui_variant") not in UI_VARIANTS:
            problems.append(f"{where}: ui_variant {s.get('ui_variant')!r} not allowed")
        if s.get("stage_code") in stage_codes:
            problems.append(f"{where}: duplicate stage_code")
        if s.get("default_order") in orders:
            problems.append(f"{where}: duplicate default_order {s.get('default_order')}")
        stage_codes.add(s.get("stage_code"))
        orders.add(s.get("default_order"))
        _check_length(problems, where, "stage_code", s.get("stage_code"), 30)
        _check_length(problems, where, "display_code", s.get("display_code"), 10)
        _check_length(problems, where, "title", s.get("title"), 255)

    # Module codes must equal the scoring taxonomy, or diagnostic scores cannot rank them.
    modules = [s.get("stage_code") for s in sorted(stages, key=lambda s: s.get("default_order") or 0)
               if s.get("stage_type") == STAGE_TYPE_MODULE]
    if modules != list(ScoringService.SALE_READY_MODULES):
        problems.append(f"module stage codes {modules} must equal {list(ScoringService.SALE_READY_MODULES)}")

    planner_stages = [s.get("stage_code") for s in stages if s.get("ui_variant") == "sale_planner"]
    if len(planner_stages) != 1:
        problems.append(f"expected exactly one stage with ui_variant 'sale_planner', found {planner_stages}")
    if not isinstance(planner, dict) or set(planner) != SALE_PLANNER_KEYS:
        problems.append(f"sale_planner config must have exactly the keys {sorted(SALE_PLANNER_KEYS)}")

    # --- task templates ---
    task_keys = set()
    for i, t in enumerate(tasks):
        where = f"task template {t.get('stage_code')}/{t.get('template_key') or i}"
        for field in ("program_type", "stage_code", "template_key", "section", "title", "default_order"):
            if t.get(field) in (None, ""):
                problems.append(f"{where}: missing '{field}'")
        if t.get("program_type") != PROGRAM_SALE_READY:
            problems.append(f"{where}: program_type must be '{PROGRAM_SALE_READY}'")
        if t.get("stage_code") not in stage_codes:
            problems.append(f"{where}: unknown stage_code")
        if t.get("section") not in TEMPLATE_SECTIONS:
            problems.append(f"{where}: section {t.get('section')!r} not in {sorted(TEMPLATE_SECTIONS)}")
        key = (t.get("stage_code"), t.get("template_key"))
        if key in task_keys:
            problems.append(f"{where}: duplicate template_key within the stage")
        task_keys.add(key)
        _check_length(problems, where, "template_key", t.get("template_key"), 100)
        _check_length(problems, where, "title", t.get("title"), 255)
        _check_length(problems, where, "group_title", t.get("group_title"), 255)

    # --- DD templates ---
    item_keys = set()
    for i, d in enumerate(dd):
        where = f"DD item {d.get('item_key') or i}"
        for field in ("program_type", "item_key", "stage_code", "category_code", "category",
                      "sub_item_code", "document", "default_order"):
            if d.get(field) in (None, ""):
                problems.append(f"{where}: missing '{field}'")
        if d.get("program_type") != PROGRAM_SALE_READY:
            problems.append(f"{where}: program_type must be '{PROGRAM_SALE_READY}'")
        if d.get("stage_code") not in stage_codes:
            problems.append(f"{where}: unknown stage_code {d.get('stage_code')!r}")
        if d.get("item_key") in item_keys:
            problems.append(f"{where}: duplicate item_key")
        item_keys.add(d.get("item_key"))
        if d.get("sub_item_code") and d.get("category_code") and \
                not str(d["sub_item_code"]).startswith(f"{d['category_code']}."):
            problems.append(f"{where}: sub_item_code {d['sub_item_code']} is not under category {d['category_code']}")
        _check_length(problems, where, "item_key", d.get("item_key"), 100)
        _check_length(problems, where, "category", d.get("category"), 255)
        _check_length(problems, where, "category_code", d.get("category_code"), 10)
        _check_length(problems, where, "sub_item_code", d.get("sub_item_code"), 10)

    if problems:
        raise FixtureError(f"{len(problems)} problem(s):\n  - " + "\n  - ".join(problems))


# ----------------------------------------------------------------------
# Upserts
# ----------------------------------------------------------------------
def _new_tally() -> dict:
    return {"created": 0, "updated": 0, "unchanged": 0, "reactivated": 0, "retired": 0}


def _apply(row, fields: dict) -> bool:
    """Set fields on an existing row; True if anything actually changed."""
    changed = False
    for name, value in fields.items():
        if getattr(row, name) != value:
            setattr(row, name, value)
            changed = True
    return changed


def _sync(db, model, existing_rows, fixture_rows, key_of_row, key_of_item, build_fields, create_kwargs) -> dict:
    """
    Upsert fixture rows onto existing rows by key; retire existing rows the
    fixtures no longer contain. Ids are never replaced.
    """
    tally = _new_tally()
    by_key = {key_of_row(row): row for row in existing_rows}
    wanted = set()

    for item in fixture_rows:
        key = key_of_item(item)
        wanted.add(key)
        fields = dict(build_fields(item), is_active=True)
        row = by_key.get(key)
        if row is None:
            db.add(model(**create_kwargs(item), **fields))
            tally["created"] += 1
            continue
        was_active = row.is_active
        changed = _apply(row, fields)
        if not was_active:
            tally["reactivated"] += 1
        elif changed:
            tally["updated"] += 1
        else:
            tally["unchanged"] += 1

    for key, row in by_key.items():
        if key not in wanted and row.is_active:
            row.is_active = False  # retire, never delete
            tally["retired"] += 1
    return tally


def _sync_stages(db, stages, planner) -> dict:
    existing = db.query(ProgramStage).filter(ProgramStage.program_type == PROGRAM_SALE_READY).all()

    def fields(s):
        return dict(
            stage_type=s["stage_type"],
            display_code=s.get("display_code"),
            title=s["title"],
            default_order=s["default_order"],
            task_creation=s["task_creation"],
            ui_variant=s.get("ui_variant"),
            # The Sale Planner's option lists and questions are that stage's screen config.
            ui_config=planner if s.get("ui_variant") == "sale_planner" else None,
        )

    return _sync(
        db, ProgramStage, existing, stages,
        key_of_row=lambda r: r.stage_code,
        key_of_item=lambda s: s["stage_code"],
        build_fields=fields,
        create_kwargs=lambda s: dict(program_type=PROGRAM_SALE_READY, stage_code=s["stage_code"]),
    )


def _sync_task_templates(db, tasks) -> dict:
    existing = db.query(ProgramTaskTemplate).filter(ProgramTaskTemplate.program_type == PROGRAM_SALE_READY).all()
    return _sync(
        db, ProgramTaskTemplate, existing, tasks,
        key_of_row=lambda r: (r.stage_code, r.template_key),
        key_of_item=lambda t: (t["stage_code"], t["template_key"]),
        build_fields=lambda t: dict(
            section=t["section"],
            group_title=t.get("group_title"),
            title=t["title"],
            default_order=t["default_order"],
        ),
        create_kwargs=lambda t: dict(
            program_type=PROGRAM_SALE_READY, stage_code=t["stage_code"], template_key=t["template_key"],
        ),
    )


def _sync_dd_templates(db, dd) -> dict:
    existing = db.query(ProgramDDTemplate).filter(ProgramDDTemplate.program_type == PROGRAM_SALE_READY).all()
    return _sync(
        db, ProgramDDTemplate, existing, dd,
        key_of_row=lambda r: r.item_key,
        key_of_item=lambda d: d["item_key"],
        build_fields=lambda d: dict(
            stage_code=d["stage_code"],
            category_code=d["category_code"],
            category=d["category"],
            sub_item_code=d["sub_item_code"],
            sub_item=d.get("sub_item"),
            document_required=d["document"],
            action_step=d.get("action_step"),
            default_order=d["default_order"],
        ),
        create_kwargs=lambda d: dict(program_type=PROGRAM_SALE_READY, item_key=d["item_key"]),
    )


# ----------------------------------------------------------------------
# Value Builder isolation
# ----------------------------------------------------------------------
def value_builder_fingerprint(db) -> tuple:
    """
    (row count, sha256) over every Program Guide content and deliverable row that
    is not Sale Ready, plus any non-Sale Ready rows in the Sale Ready tables.
    Includes updated_at, so any write to one of these rows changes the hash.
    """
    rows = []
    for model, key in ((ProgramModuleContent, "module_code"), (ProgramModuleDeliverable, "deliverable_key")):
        for r in db.query(model).filter(model.program_type != PROGRAM_SALE_READY).order_by(model.id):
            rows.append((model.__tablename__, str(r.id), getattr(r, key), r.is_active, str(r.updated_at)))
    for model in (ProgramStage, ProgramTaskTemplate, ProgramDDTemplate):
        for r in db.query(model).filter(model.program_type != PROGRAM_SALE_READY).order_by(model.id):
            rows.append((model.__tablename__, str(r.id), r.is_active, str(r.updated_at)))
    return len(rows), hashlib.sha256(json.dumps(rows).encode()).hexdigest()


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------
def _sync_guide(db, guide: dict) -> dict:
    """
    Seed the program guide: program-level content plus each stage's block.

    Only fills what is empty. Once an admin has edited a stage guide through
    Sale Ready Management, re-seeding leaves it alone - the fixtures are the
    starting content, not the authority.
    """
    tally = _new_tally()

    row = db.query(ProgramGuideContent).filter(
        ProgramGuideContent.program_type == PROGRAM_SALE_READY
    ).first()
    if row is None:
        db.add(ProgramGuideContent(program_type=PROGRAM_SALE_READY, content=guide["program"], is_active=True))
        tally["created"] += 1
    else:
        tally["unchanged"] += 1

    by_code = {
        st.stage_code: st
        for st in db.query(ProgramStage).filter(ProgramStage.program_type == PROGRAM_SALE_READY)
    }
    for stage_code, block in guide["stages"].items():
        stage = by_code.get(stage_code)
        if stage is None:
            continue
        if stage.guide:
            tally["unchanged"] += 1
            continue
        stage.guide = block
        tally["updated"] += 1
    return tally


def _templates_are_empty(db) -> bool:
    """True when no Sale Ready template rows exist at all - a fresh environment."""
    for model in (ProgramStage, ProgramTaskTemplate, ProgramDDTemplate):
        if db.query(model).filter(model.program_type == PROGRAM_SALE_READY).first() is not None:
            return False
    return True


def seed_from_fixtures(fixture_dir: str = FIXTURE_DIR, db=None, dry_run: bool = False,
                       force: bool = False) -> dict:
    """
    Seed the template tables. Pass `db` to run inside an existing session
    (the tests do, so everything rolls back); otherwise one is opened here.

    Admins can now edit this content through Sale Ready Management, so the
    destructive sync - which upserts every fixture row and retires anything the
    fixtures no longer list - only runs on an empty environment unless `force`
    is given. Guide blocks are never overwritten once set.
    """
    fixtures = load_fixtures(fixture_dir)
    validate_fixtures(fixtures)

    owns_session = db is None
    db = db or SessionLocal()
    try:
        vb_before = value_builder_fingerprint(db)

        if not force and not _templates_are_empty(db):
            result = {name: _new_tally() for name in ("stages", "task_templates", "dd_templates")}
            result["skipped"] = True
        else:
            result = {
                "stages": _sync_stages(db, fixtures["stages"], fixtures["sale_planner"]),
                "task_templates": _sync_task_templates(db, fixtures["tasks"]),
                "dd_templates": _sync_dd_templates(db, fixtures["dd"]),
            }
            result["skipped"] = False
        db.flush()
        result["guide"] = _sync_guide(db, fixtures["guide"])
        db.flush()

        vb_after = value_builder_fingerprint(db)
        if vb_after != vb_before:
            db.rollback()
            raise RuntimeError("Value Builder rows changed during the Sale Ready seed; rolled back")
        result["value_builder_rows"] = vb_before[0]
        result["fixture_counts"] = {"stages": len(fixtures["stages"]),
                                    "task_templates": len(fixtures["tasks"]),
                                    "dd_templates": len(fixtures["dd"])}

        if dry_run:
            db.rollback()
        else:
            db.commit()
        return result
    finally:
        if owns_session:
            db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", default=FIXTURE_DIR, help="Directory holding the Sale Ready fixtures")
    parser.add_argument("--dry-run", action="store_true", help="Validate and roll back without writing")
    parser.add_argument("--force", action="store_true",
                        help="Re-sync templates even when rows exist. OVERWRITES admin edits.")
    args = parser.parse_args()

    try:
        result = seed_from_fixtures(args.dir, dry_run=args.dry_run, force=args.force)
    except FixtureError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print("DRY RUN - nothing written." if args.dry_run else "Seeded.")
    if result.get("skipped"):
        print("  Templates already present: left untouched (admin-owned). Use --force to re-sync.")
    g = result["guide"]
    print(f"  {'guide':15s} {g['created']} created, {g['updated']} filled, {g['unchanged']} left as-is")
    for name in ("stages", "task_templates", "dd_templates"):
        t = result[name]
        print(f"  {name:15s} fixture={result['fixture_counts'][name]:3d}  "
              f"{t['created']} created, {t['updated']} updated, {t['unchanged']} unchanged, "
              f"{t['reactivated']} reactivated, {t['retired']} retired")
    print(f"  Value Builder rows checked: {result['value_builder_rows']}, unchanged")


if __name__ == "__main__":
    main()

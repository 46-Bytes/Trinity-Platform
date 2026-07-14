"""
Seed/update Sale Ready program template tables from JSON fixtures.

Idempotent upserts:
  - program_stage         keyed on (program_type, stage_code)
  - program_task_template keyed on (program_type, stage_code, section, title)
  - program_dd_template   keyed on (program_type, module_code, category, sub_item)

Re-run whenever the fixtures change (e.g. once BBA delivers real content).

Usage (from the backend/ directory):
    python scripts/seed_sale_ready_content.py
    python scripts/seed_sale_ready_content.py --dir files/sale_ready
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.sale_ready import ProgramStage, ProgramTaskTemplate, ProgramDDTemplate

DEFAULT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "files", "sale_ready",
)


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_stages(db, entries):
    created = updated = 0
    for e in entries:
        row = (
            db.query(ProgramStage)
            .filter(ProgramStage.program_type == e["program_type"], ProgramStage.stage_code == e["stage_code"])
            .first()
        )
        if row:
            row.stage_type = e["stage_type"]
            row.default_order = e["default_order"]
            row.title = e["title"]
            row.description = e.get("description")
            row.is_active = e.get("is_active", True)
            updated += 1
        else:
            db.add(ProgramStage(
                program_type=e["program_type"], stage_code=e["stage_code"], stage_type=e["stage_type"],
                default_order=e["default_order"], title=e["title"], description=e.get("description"),
                is_active=e.get("is_active", True),
            ))
            created += 1
    return created, updated


def seed_task_templates(db, entries):
    created = updated = 0
    for e in entries:
        row = (
            db.query(ProgramTaskTemplate)
            .filter(
                ProgramTaskTemplate.program_type == e["program_type"],
                ProgramTaskTemplate.stage_code == e["stage_code"],
                ProgramTaskTemplate.section == e["section"],
                ProgramTaskTemplate.title == e["title"],
            )
            .first()
        )
        if row:
            row.description = e.get("description")
            row.priority = e.get("priority", "medium")
            row.default_order = e.get("default_order", 0)
            row.due_offset_days = e.get("due_offset_days")
            row.is_active = e.get("is_active", True)
            updated += 1
        else:
            db.add(ProgramTaskTemplate(
                program_type=e["program_type"], stage_code=e["stage_code"], section=e["section"],
                title=e["title"], description=e.get("description"), priority=e.get("priority", "medium"),
                default_order=e.get("default_order", 0), due_offset_days=e.get("due_offset_days"),
                is_active=e.get("is_active", True),
            ))
            created += 1
    return created, updated


def seed_dd_templates(db, entries):
    created = updated = 0
    for e in entries:
        row = (
            db.query(ProgramDDTemplate)
            .filter(
                ProgramDDTemplate.program_type == e["program_type"],
                ProgramDDTemplate.module_code == e["module_code"],
                ProgramDDTemplate.category == e["category"],
                ProgramDDTemplate.sub_item == e.get("sub_item"),
            )
            .first()
        )
        if row:
            row.document_required = e.get("document_required")
            row.action_step = e.get("action_step")
            row.default_order = e.get("default_order", 0)
            row.is_active = e.get("is_active", True)
            updated += 1
        else:
            db.add(ProgramDDTemplate(
                program_type=e["program_type"], module_code=e["module_code"], category=e["category"],
                sub_item=e.get("sub_item"), document_required=e.get("document_required"),
                action_step=e.get("action_step"), default_order=e.get("default_order", 0),
                is_active=e.get("is_active", True),
            ))
            created += 1
    return created, updated


def main(directory):
    db = SessionLocal()
    try:
        s_c, s_u = seed_stages(db, _load(os.path.join(directory, "stages.json")))
        t_c, t_u = seed_task_templates(db, _load(os.path.join(directory, "task_templates.json")))
        d_c, d_u = seed_dd_templates(db, _load(os.path.join(directory, "dd_templates.json")))
        db.commit()
        print(f"program_stage:         {s_c} created, {s_u} updated")
        print(f"program_task_template: {t_c} created, {t_u} updated")
        print(f"program_dd_template:   {d_c} created, {d_u} updated")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=DEFAULT_DIR, help="Directory holding the JSON fixtures")
    args = parser.parse_args()
    main(args.dir)

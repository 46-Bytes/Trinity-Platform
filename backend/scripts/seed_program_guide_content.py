"""
Seed/update program_module_content from a JSON fixture.

Idempotent: upserts rows keyed on (program_type, module_code). Re-run this
whenever the fixture file changes (e.g. once the client delivers real copy).

Usage (from the backend/ directory):
    python scripts/seed_program_guide_content.py
    python scripts/seed_program_guide_content.py --file files/program_guide/value_builder_modules.json
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.program_guide import ProgramModuleContent

DEFAULT_FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "files", "program_guide", "value_builder_modules.json",
)


def seed_from_file(fixture_path: str) -> None:
    with open(fixture_path, "r", encoding="utf-8") as f:
        modules = json.load(f)

    db = SessionLocal()
    try:
        created, updated = 0, 0
        for entry in modules:
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
                existing.deliverables = entry.get("deliverables")
                existing.is_active = entry.get("is_active", True)
                updated += 1
            else:
                db.add(ProgramModuleContent(
                    program_type=entry["program_type"],
                    module_code=entry["module_code"],
                    display_order=entry["display_order"],
                    title=entry["title"],
                    purpose=entry.get("purpose"),
                    preparation_checklist=entry.get("preparation_checklist"),
                    recommended_tools=entry.get("recommended_tools"),
                    deliverables=entry.get("deliverables"),
                    is_active=entry.get("is_active", True),
                ))
                created += 1
        db.commit()
        print(f"Seeded program_module_content from {fixture_path}: {created} created, {updated} updated.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=DEFAULT_FIXTURE, help="Path to the JSON fixture to seed from")
    args = parser.parse_args()
    seed_from_file(args.file)

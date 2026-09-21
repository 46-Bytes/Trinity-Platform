"""
Create missing phase tasks on Sale Ready engagements that were already initialized.

Sale Ready creates a stage's preset tasks once, when that engagement's stage row
is first created. That is deliberate: it is what stops a task an advisor deleted
from reappearing on the next read. The cost is that a template added to an
existing stage later - the four Close-out tasks the brief confirmed (C2) - never
reaches engagements that were set up before it existed. This script closes that
gap, once, for stages whose tasks are created with the engagement.

Idempotent and non-destructive:

  - A template is skipped when the engagement already has a task from it,
    INCLUDING a soft-deleted one. Deleting a task is a decision; a backfill must
    not undo it.
  - Nothing existing is ever updated. The script only inserts.
  - Engagements with no stage rows are skipped entirely: they have not been
    opened yet, and their first read creates everything from the current
    templates anyway.

Run it after seeding the new templates (scripts/seed_sale_ready_program.py).

Usage (from backend/):
    python scripts/backfill_sale_ready_phase_tasks.py --dry-run
    python scripts/backfill_sale_ready_phase_tasks.py
    python scripts/backfill_sale_ready_phase_tasks.py --stage CLOSEOUT
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.engagement import Engagement
from app.models.sale_ready import EngagementStageState, ProgramStage, ProgramTaskTemplate
from app.models.task import Task
from app.services.program_registry import PROGRAM_SALE_READY
from app.services.sale_ready_rules import SECTION_MUST_DO
from app.services.sale_ready_service import TASK_CREATION_ON_ENGAGEMENT


def stages_created_with_engagement(db, only_stage=None):
    query = db.query(ProgramStage).filter(
        ProgramStage.program_type == PROGRAM_SALE_READY,
        ProgramStage.task_creation == TASK_CREATION_ON_ENGAGEMENT,
        ProgramStage.is_active == True,  # noqa: E712
    )
    if only_stage:
        query = query.filter(ProgramStage.stage_code == only_stage)
    return [s.stage_code for s in query.order_by(ProgramStage.default_order)]


def backfill(db, only_stage=None, dry_run=False):
    stage_codes = stages_created_with_engagement(db, only_stage)
    if not stage_codes:
        raise SystemExit(f"No active Sale Ready stages found{f' for {only_stage}' if only_stage else ''}. Seed first.")

    templates = db.query(ProgramTaskTemplate).filter(
        ProgramTaskTemplate.program_type == PROGRAM_SALE_READY,
        ProgramTaskTemplate.is_active == True,  # noqa: E712
        ProgramTaskTemplate.stage_code.in_(stage_codes),
    ).order_by(ProgramTaskTemplate.stage_code, ProgramTaskTemplate.default_order).all()

    engagements = db.query(Engagement).filter(
        Engagement.tool == PROGRAM_SALE_READY,
        Engagement.is_deleted == False,  # noqa: E712
    ).all()

    created, skipped_uninitialised, per_stage = 0, 0, {}
    for engagement in engagements:
        initialised = db.query(EngagementStageState).filter_by(engagement_id=engagement.id).count()
        if not initialised:
            skipped_uninitialised += 1
            continue

        # Every template this engagement already has a task from, soft-deleted included.
        taken = {
            row[0] for row in db.query(Task.source_task_template_id).filter(
                Task.engagement_id == engagement.id,
                Task.source_task_template_id.isnot(None),
            )
        }
        state_by_stage = {
            s.stage_code: s for s in db.query(EngagementStageState).filter_by(engagement_id=engagement.id)
        }
        creator_id = engagement.primary_advisor_id
        if creator_id is None:
            # tasks.created_by_user_id is NOT NULL and there is no sensible stand-in.
            print(f"  ! {engagement.engagement_name}: no primary advisor, skipped")
            continue

        for template in templates:
            if template.id in taken:
                continue
            state = state_by_stage.get(template.stage_code)
            lead = (state.lead_advisor_id if state else None) or engagement.primary_advisor_id
            db.add(Task(
                engagement_id=engagement.id,
                created_by_user_id=creator_id,
                title=template.title,
                description=template.description,
                task_type="manual",
                status="pending",
                priority=template.priority or "medium",
                module_reference=template.stage_code,
                section=template.section,
                source_task_template_id=template.id,
                assigned_to_user_ids=[lead] if lead and template.section == SECTION_MUST_DO else None,
            ))
            created += 1
            per_stage[template.stage_code] = per_stage.get(template.stage_code, 0) + 1

    if dry_run:
        db.rollback()
    else:
        db.commit()
    return {
        "engagements": len(engagements),
        "skipped_uninitialised": skipped_uninitialised,
        "created": created,
        "per_stage": per_stage,
        "stages_considered": stage_codes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stage", help="Limit to one stage code, e.g. CLOSEOUT")
    parser.add_argument("--dry-run", action="store_true", help="Report what would be created, then roll back")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = backfill(db, only_stage=args.stage, dry_run=args.dry_run)
    finally:
        db.close()

    print("DRY RUN - nothing written." if args.dry_run else "Backfilled.")
    print(f"  stages considered      : {', '.join(result['stages_considered'])}")
    print(f"  Sale Ready engagements : {result['engagements']}")
    print(f"  skipped (not opened yet): {result['skipped_uninitialised']}")
    print(f"  tasks created          : {result['created']}")
    for stage, count in sorted(result["per_stage"].items()):
        print(f"    {stage:12s} {count}")


if __name__ == "__main__":
    main()

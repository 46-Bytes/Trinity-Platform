"""
Freeze the program guide onto Sale Ready engagements that started before snapshots.

Every Sale Ready engagement reads its own frozen copy of the program guide, so
an admin editing the guide changes what future engagements get and nothing else.
Engagements initialized before that copy existed have no row yet; without one
they would fall back to the live master and so would follow admin edits - the
behaviour the brief rules out.

This writes the current master as their snapshot, once.

Idempotent and non-destructive:

  - An engagement that already has a snapshot is skipped. A snapshot is never
    rewritten, here or anywhere else.
  - Engagements with no Sale Ready stage rows are skipped: they have not been
    opened yet, and their first read writes a snapshot from the current master.
  - Nothing else is read or written. Tasks, DD items and stage state are untouched.

Run it after scripts/seed_sale_ready_program.py.

Usage (from backend/):
    python scripts/backfill_sale_ready_guide.py --dry-run
    python scripts/backfill_sale_ready_guide.py
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models.engagement import Engagement  # noqa: E402
from app.models.sale_ready import EngagementSaleReadyGuide, EngagementStageState  # noqa: E402
from app.services.program_registry import PROGRAM_SALE_READY  # noqa: E402
from app.services.sale_ready_service import get_sale_ready_service  # noqa: E402


def backfill(db, dry_run: bool = False) -> dict:
    service = get_sale_ready_service(db)
    content = service.build_guide_content()
    if not content.get("stages"):
        raise RuntimeError(
            "No Sale Ready stages found. Run scripts/seed_sale_ready_program.py first."
        )

    engagements = (
        db.query(Engagement)
        .filter(Engagement.tool == PROGRAM_SALE_READY, Engagement.is_deleted == False)  # noqa: E712
        .order_by(Engagement.created_at.asc())
        .all()
    )

    tally = {"written": 0, "already_had_one": 0, "not_initialized": 0}
    for engagement in engagements:
        has_snapshot = db.query(EngagementSaleReadyGuide).filter(
            EngagementSaleReadyGuide.engagement_id == engagement.id
        ).first() is not None
        if has_snapshot:
            tally["already_had_one"] += 1
            continue

        initialized = db.query(EngagementStageState).filter(
            EngagementStageState.engagement_id == engagement.id
        ).first() is not None
        if not initialized:
            # Never opened: its first read will write the snapshot itself.
            tally["not_initialized"] += 1
            continue

        db.add(EngagementSaleReadyGuide(engagement_id=engagement.id, content=content))
        tally["written"] += 1
        print(f"  snapshot written for {engagement.id} ({engagement.engagement_name})")

    tally["engagements"] = len(engagements)
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return tally


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tally = backfill(db, dry_run=args.dry_run)
    finally:
        db.close()

    print("DRY RUN - nothing written." if args.dry_run else "Done.")
    print(f"  Sale Ready engagements : {tally['engagements']}")
    print(f"  snapshots written      : {tally['written']}")
    print(f"  already had one        : {tally['already_had_one']}")
    print(f"  not initialized yet    : {tally['not_initialized']}")


if __name__ == "__main__":
    main()

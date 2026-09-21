"""
Move uploaded profile pictures into files/public and repoint users.picture.

backend/files used to be mounted whole at /files, so every upload, prompt,
scoring map and export was downloadable by anyone who knew the path. main.py
now mounts only backend/files/public, and avatars - the one thing an <img> must
fetch without a bearer token - are written there.

Pictures uploaded before that change still point at
/files/uploads/users/{user_id}/profilepicture/{file}, which is no longer served.
This script moves each one to files/public/avatars/{user_id}/{file} and updates
the row. Run it once per environment, after deploying the change.

Idempotent and non-destructive:

  - Rows already pointing at /files/public/ are left alone.
  - Auth0/Google URLs (http...) are left alone.
  - A row whose file is missing on disk is reported and left alone, so the
    broken link stays visible rather than being silently cleared.
  - The file is copied, then the row updated, then the original removed only
    once both succeeded.

Usage (from backend/):
    python scripts/move_avatars_to_public.py --dry-run
    python scripts/move_avatars_to_public.py
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.user import User

FILES_DIR = Path(__file__).resolve().parents[1] / "files"
OLD_PREFIX = "/files/"
NEW_PREFIX = "/files/public/"


def move_avatars(db, dry_run=False):
    users = db.query(User).filter(User.picture.isnot(None), User.picture != "").all()
    moved, already_public, external, missing = 0, 0, 0, []

    for user in users:
        picture = user.picture
        if picture.startswith(NEW_PREFIX):
            already_public += 1
            continue
        if not picture.startswith(OLD_PREFIX):
            external += 1  # Auth0, Google, or anything else remote
            continue

        source = FILES_DIR / picture[len(OLD_PREFIX):]
        if not source.is_file():
            missing.append((str(user.id), picture))
            continue

        destination_dir = FILES_DIR / "public" / "avatars" / str(user.id)
        destination = destination_dir / source.name
        new_picture = f"{NEW_PREFIX}avatars/{user.id}/{source.name}"

        if dry_run:
            print(f"  would move {picture} -> {new_picture}")
            moved += 1
            continue

        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        user.picture = new_picture
        db.commit()
        try:
            source.unlink()
        except OSError as e:
            # The row already points at the copy, so a stale original is
            # untidy rather than harmful. Say so instead of failing the run.
            print(f"  ! copied but could not remove {source}: {e}")
        moved += 1

    if dry_run:
        db.rollback()
    return {"moved": moved, "already_public": already_public, "external": external, "missing": missing}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Report what would move, change nothing")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = move_avatars(db, dry_run=args.dry_run)
    finally:
        db.close()

    print("DRY RUN - nothing written." if args.dry_run else "Done.")
    print(f"  moved to files/public : {result['moved']}")
    print(f"  already public        : {result['already_public']}")
    print(f"  external (http)       : {result['external']}")
    if result["missing"]:
        print(f"  file missing on disk  : {len(result['missing'])} (left as they are)")
        for user_id, picture in result["missing"]:
            print(f"    {user_id} -> {picture}")


if __name__ == "__main__":
    main()

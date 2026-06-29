"""
One-shot script to create (or fix) a super_admin user and send a password setup email.

Handles the case where the Auth0 account already exists:
  1. Looks up the user in Auth0 by email.
  2. Updates their app_metadata role to super_admin.
  3. Creates / updates the local DB record.
  4. Sends a fresh password-setup email.

Usage:
    cd backend
    python seed/add_superadmin.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.media import Media  # noqa: F401 — keeps SQLAlchemy happy
from app.services.auth0_management import Auth0Management


EMAIL = "saadullahkhan030121@gmail.com"
FIRST_NAME = "Saadullah"
LAST_NAME = "Khan"
ROLE = UserRole.SUPER_ADMIN


def get_auth0_user_by_email(email: str) -> dict:
    token = Auth0Management.get_management_token()
    from app.config import settings
    url = f"https://{settings.AUTH0_DOMAIN}/api/v2/users-by-email"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(url, params={"email": email}, headers=headers)
    resp.raise_for_status()
    users = resp.json()
    if not users:
        raise Exception(f"No Auth0 user found with email {email}")
    return users[0]


def main():
    db = SessionLocal()
    try:
        print(f"Looking up Auth0 user for {EMAIL} ...")
        auth0_user = get_auth0_user_by_email(EMAIL)
        auth0_id = auth0_user["user_id"]
        print(f"  Found Auth0 user: {auth0_id}")

        # Update role in Auth0 app_metadata
        print(f"  Updating Auth0 role to super_admin ...")
        Auth0Management.update_user_role(auth0_id, ROLE.value)
        print(f"  Auth0 role updated.")

        # Sync local DB record
        db_user = db.query(User).filter(User.email == EMAIL).first()
        if db_user:
            print(f"  Found existing DB user (id={db_user.id}). Updating role ...")
            db_user.role = ROLE
            db_user.is_active = True
            db_user.is_deleted = False
            if not db_user.auth0_id:
                db_user.auth0_id = auth0_id
        else:
            print(f"  No DB record — creating one ...")
            db_user = User(
                auth0_id=auth0_id,
                email=EMAIL,
                first_name=FIRST_NAME,
                last_name=LAST_NAME,
                name=f"{FIRST_NAME} {LAST_NAME}",
                role=ROLE,
                is_active=True,
                is_deleted=False,
                email_verified=False,
            )
            db.add(db_user)

        db.commit()
        db.refresh(db_user)
        print(f"  DB record saved (id={db_user.id}, role={db_user.role}).")

        # Send a fresh password-setup email
        print(f"\nSending password-setup email to {EMAIL} ...")
        Auth0Management.send_password_setup_email(
            auth0_user_id=auth0_id,
            email=EMAIL,
            user_name=f"{FIRST_NAME} {LAST_NAME}",
        )
        print(f"Password-setup email sent successfully.")
        print(f"\nDone. {EMAIL} is now a super_admin and has received the setup email.")

    except Exception as e:
        db.rollback()
        print(f"\nError: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

"""
Seed script to create two client users for testing/demo purposes.
Run this script to populate the database with sample client users.

Usage:
    python seed_clients.py
"""
import sys
from pathlib import Path

# Add the app directory to the path so we can import modules
sys.path.insert(0, str(Path(__file__).parent))

from app.database import SessionLocal
from app.models.user import User, UserRole
from datetime import datetime


def seed_clients():
    """Create two client users in the database."""
    db = SessionLocal()
    
    try:
        # Define the two client users to create
        clients_to_create = [
            {
                "auth0_id": "auth0|seed_client_1",
                "email": "client1@example.com",
                "name": "John Doe",
                "given_name": "John",
                "family_name": "Doe",
                "role": UserRole.CLIENT,
                "email_verified": True,
                "is_active": True,
            },
            {
                "auth0_id": "auth0|seed_client_2",
                "email": "client2@example.com",
                "name": "Jane Smith",
                "given_name": "Jane",
                "family_name": "Smith",
                "role": UserRole.CLIENT,
                "email_verified": True,
                "is_active": True,
            },
        ]
        
        created_count = 0
        skipped_count = 0
        
        for client_data in clients_to_create:
            # Check if user already exists by email or auth0_id
            existing_user = db.query(User).filter(
                (User.email == client_data["email"]) | 
                (User.auth0_id == client_data["auth0_id"])
            ).first()
            
            if existing_user:
                print(f"⚠️  User with email '{client_data['email']}' or auth0_id '{client_data['auth0_id']}' already exists. Skipping...")
                skipped_count += 1
                continue
            
            # Create new client user
            client = User(**client_data)
            db.add(client)
            created_count += 1
            print(f"✅ Created client user: {client_data['name']} ({client_data['email']})")
        
        if created_count > 0:
            db.commit()
            print(f"\n🎉 Successfully created {created_count} client user(s)!")
        else:
            print(f"\nℹ️  No new users created. {skipped_count} user(s) already exist.")
        
        if skipped_count > 0:
            print(f"   Skipped {skipped_count} existing user(s).")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding clients: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding client users...\n")
    seed_clients()
    print("\n✨ Done!")


"""
Seed script to create an admin user for testing/demo purposes.
Run this script to populate the database with an admin user.

IMPORTANT: This creates a user in the database, but you still need to:
1. Create the user in Auth0 with the same email, OR
2. Use a development bypass if available

Usage:
    python seed_admin.py

Credentials:
    Email: admin@trinity.ai
    Password: (Set in Auth0 - see instructions below)
"""
import sys
from pathlib import Path

# Add the backend directory to the path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import User, UserRole, Media  # Import from package to ensure all models are loaded
from datetime import datetime


def seed_admin():
    """Create an admin user in the database."""
    db = SessionLocal()
    
    try:
        # Define the admin user to create
        admin_data = {
            "auth0_id": "auth0|seed_admin",
            "email": "admin@trinity.ai",
            "name": "Trinity Admin",
            "given_name": "Trinity",
            "family_name": "Admin",
            "nickname": "admin",
            "role": UserRole.ADMIN,
            "email_verified": True,
            "is_active": True,
        }
        
        # Check if user already exists by email or auth0_id
        existing_user = db.query(User).filter(
            (User.email == admin_data["email"]) | 
            (User.auth0_id == admin_data["auth0_id"])
        ).first()
        
        if existing_user:
            print(f"⚠️  Admin user with email '{admin_data['email']}' or auth0_id '{admin_data['auth0_id']}' already exists.")
            print(f"   Current role: {existing_user.role.value}")
            
            # Update role to ADMIN if it's not already
            if existing_user.role != UserRole.ADMIN:
                existing_user.role = UserRole.ADMIN
                db.commit()
                print(f"✅ Updated user role to ADMIN")
            else:
                print(f"   User already has ADMIN role.")
            
            print(f"\n📧 Login Credentials:")
            print(f"   Email: {admin_data['email']}")
            print(f"   Auth0 ID: {admin_data['auth0_id']}")
            print(f"\n⚠️  IMPORTANT: To log in, you need to:")
            print(f"   1. Create this user in Auth0 with email: {admin_data['email']}")
            print(f"   2. Set the password in Auth0 dashboard")
            print(f"   3. Add app_metadata: {{'role': 'admin'}} in Auth0")
            return
        
        # Create new admin user
        admin = User(**admin_data)
        db.add(admin)
        db.commit()
        
        print(f"✅ Created admin user: {admin_data['name']} ({admin_data['email']})")
        print(f"\n📧 Login Credentials:")
        print(f"   Email: {admin_data['email']}")
        print(f"   Auth0 ID: {admin_data['auth0_id']}")
        print(f"   Role: {admin_data['role'].value}")
        print(f"\n⚠️  IMPORTANT: To log in, you need to:")
        print(f"   1. Create this user in Auth0 with email: {admin_data['email']}")
        print(f"   2. Set the password in Auth0 dashboard")
        print(f"   3. Add app_metadata: {{'role': 'admin'}} in Auth0")
        print(f"\n   OR use the Auth0 Management API to create the user programmatically.")
        print(f"\n🎉 Admin user created successfully!")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding admin: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding admin user...\n")
    seed_admin()
    print("\n✨ Done!")


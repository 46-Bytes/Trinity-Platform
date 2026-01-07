"""
Seed script to create a firm with a specified admin user.
Run this script to create a firm account with the admin user as the firm admin.

Usage:
    python seed_firm.py
"""
import sys
from pathlib import Path
from uuid import UUID

# Add the backend directory to the path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.firm import Firm
from app.models.subscription import Subscription
from app.services.firm_service import FirmService
from datetime import datetime


def seed_firm():
    """Create a firm with the specified admin user as firm admin."""
    db = SessionLocal()
    
    try:
        # The admin user ID to use as firm admin
        admin_user_id = UUID("6613cc9f-7dbe-428d-80d4-c6925e78a917")
        
        # Check if admin user exists
        admin_user = db.query(User).filter(User.id == admin_user_id).first()
        if not admin_user:
            print(f"❌ User with ID {admin_user_id} not found!")
            return
        
        print(f"✅ Found admin user: {admin_user.email} (Role: {admin_user.role.value})")
        
        # Check if user is already in a firm
        firm = None
        if admin_user.firm_id:
            # Use raw SQL to check firm existence to avoid column errors
            from sqlalchemy import text
            result = db.execute(
                text("SELECT id, firm_name FROM firms WHERE id = :firm_id"),
                {"firm_id": admin_user.firm_id}
            ).first()
            if result:
                firm_id = result[0]
                firm_name = result[1]
                print(f"⚠️  User is already part of firm: {firm_name}")
                print(f"   Firm ID: {firm_id}")
                # Try to get firm object (will fail if clients column doesn't exist)
                try:
                    firm = db.query(Firm).filter(Firm.id == firm_id).first()
                except Exception:
                    # Column doesn't exist yet, we'll handle it later
                    firm = None
                    print(f"   Note: 'clients' column may not exist yet")
        
        # Check if a firm already exists with this admin (if we don't have it yet)
        if not firm:
            from sqlalchemy import text
            result = db.execute(
                text("SELECT id, firm_name FROM firms WHERE firm_admin_id = :admin_id"),
                {"admin_id": admin_user_id}
            ).first()
            if result:
                firm_id = result[0]
                firm_name = result[1]
                print(f"⚠️  Firm already exists with this admin: {firm_name}")
                print(f"   Firm ID: {firm_id}")
                try:
                    firm = db.query(Firm).filter(Firm.id == firm_id).first()
                except Exception:
                    firm = None
                    print(f"   Note: 'clients' column may not exist yet")
        
        # Update user role to FIRM_ADMIN if not already
        if admin_user.role != UserRole.FIRM_ADMIN:
            print(f"📝 Updating user role from {admin_user.role.value} to firm_admin...")
            admin_user.role = UserRole.FIRM_ADMIN
            db.commit()
            print("✅ User role updated to FIRM_ADMIN")
        
        # Create firm if it doesn't exist
        if not firm:
            firm_service = FirmService(db)
            firm = firm_service.create_firm(
                firm_name="Trinity Advisory Firm",
                firm_admin_id=admin_user_id,
                seat_count=10,
                billing_email=admin_user.email
            )
            print(f"\n🎉 Successfully created firm!")
        else:
            print(f"\n📝 Updating existing firm...")
        
        # Refresh to get subscription_id
        db.refresh(firm)
        
        # Find the two clients by auth0_id
        client1 = db.query(User).filter(User.auth0_id == "auth0|seed_client_1").first()
        client2 = db.query(User).filter(User.auth0_id == "auth0|seed_client_2").first()
        
        # Check if clients column exists in database
        from sqlalchemy import text, inspect
        inspector = inspect(db.bind)
        columns = [col['name'] for col in inspector.get_columns('firms')]
        has_clients_column = 'clients' in columns
        
        if has_clients_column and firm:
            # Initialize clients array if None
            if firm.clients is None:
                firm.clients = []
            
            # Add clients to the array if they exist and aren't already in it
            client_ids_to_add = []
            if client1:
                if client1.id not in firm.clients:
                    firm.clients.append(client1.id)
                    client_ids_to_add.append(client1.id)
                    print(f"✅ Added client 1: {client1.email} (ID: {client1.id})")
                else:
                    print(f"ℹ️  Client 1 already in firm: {client1.email}")
            else:
                print(f"⚠️  Client 1 (auth0|seed_client_1) not found. Run seed_clients.py first.")
            
            if client2:
                if client2.id not in firm.clients:
                    firm.clients.append(client2.id)
                    client_ids_to_add.append(client2.id)
                    print(f"✅ Added client 2: {client2.email} (ID: {client2.id})")
                else:
                    print(f"ℹ️  Client 2 already in firm: {client2.email}")
            else:
                print(f"⚠️  Client 2 (auth0|seed_client_2) not found. Run seed_clients.py first.")
            
            # Commit the changes
            if client_ids_to_add:
                db.commit()
                db.refresh(firm)
                print(f"✅ Updated firm clients array with {len(client_ids_to_add)} client(s)")
        elif not has_clients_column:
            # Column doesn't exist yet - provide SQL to run after migration
            print("\n⚠️  'clients' column doesn't exist yet. Please run migration first.")
            if firm:
                firm_id = firm.id if hasattr(firm, 'id') else admin_user.firm_id
                if client1 and client2:
                    print(f"\n   After migration, run this SQL to add clients:")
                    print(f"   UPDATE firms SET clients = ARRAY['{client1.id}'::UUID, '{client2.id}'::UUID] WHERE id = '{firm_id}'::UUID;")
                elif client1:
                    print(f"\n   After migration, run this SQL to add client:")
                    print(f"   UPDATE firms SET clients = ARRAY['{client1.id}'::UUID] WHERE id = '{firm_id}'::UUID;")
                elif client2:
                    print(f"\n   After migration, run this SQL to add client:")
                    print(f"   UPDATE firms SET clients = ARRAY['{client2.id}'::UUID] WHERE id = '{firm_id}'::UUID;")
                else:
                    print(f"   No clients found. Run seed_clients.py first.")
            else:
                print(f"   Firm not found or not accessible.")
        
        # Get subscription details
        subscription = None
        if firm.subscription_id:
            subscription = db.query(Subscription).filter(Subscription.id == firm.subscription_id).first()
        
        print(f"\n📊 Firm Summary:")
        print(f"   Firm Name: {firm.firm_name}")
        print(f"   Firm ID: {firm.id}")
        print(f"   Firm Admin: {admin_user.email}")
        print(f"   Seat Count: {firm.seat_count}")
        print(f"   Clients in firm: {len(firm.clients) if firm.clients else 0}")
        if firm.subscription_id:
            print(f"   Subscription ID: {firm.subscription_id}")
            if subscription:
                print(f"   Subscription Plan: {subscription.plan_name}")
                print(f"   Subscription Status: {subscription.status}")
        else:
            print(f"   ⚠️  Warning: Subscription ID not set!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding firm: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Seeding firm with admin user...\n")
    seed_firm()
    print("\n✨ Done!")


"""
Seed script to create a subscription for an existing firm.
Run this script to create a subscription for a firm that doesn't have one.

Usage:
    python seed_subscription.py
"""
import sys
from pathlib import Path
from uuid import UUID
from datetime import datetime, timedelta

# Add the backend directory to the path so we can import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models.firm import Firm
from app.models.subscription import Subscription


def seed_subscription(firm_id: UUID = None):
    """Create a subscription for a firm."""
    db = SessionLocal()
    
    try:
        # If firm_id is provided, use it; otherwise find the first firm without subscription
        if firm_id:
            firm = db.query(Firm).filter(Firm.id == firm_id).first()
        else:
            firm = db.query(Firm).filter(Firm.subscription_id == None).first()
        
        if not firm:
            if firm_id:
                print(f"❌ Firm with ID {firm_id} not found!")
            else:
                print("❌ No firm found without a subscription!")
            return
        
        # Check if firm already has a subscription linked
        if firm.subscription_id:
            existing_sub = db.query(Subscription).filter(Subscription.id == firm.subscription_id).first()
            if existing_sub:
                print(f"⚠️  Firm already has a subscription linked: {existing_sub.id}")
                print(f"   Plan: {existing_sub.plan_name}, Status: {existing_sub.status}")
                return
        
        # Check if subscription already exists for this firm
        existing_sub = db.query(Subscription).filter(Subscription.firm_id == firm.id).first()
        if existing_sub:
            # Link existing subscription to firm
            print(f"📝 Found existing subscription, linking to firm...")
            subscription = existing_sub
            firm.subscription_id = subscription.id
        else:
            # Create new subscription
            subscription = Subscription(
                firm_id=firm.id,
                plan_name="professional",
                seat_count=firm.seat_count,
                monthly_price=299.00,  # Base price per month
                status="active",
                current_period_start=datetime.utcnow(),
                current_period_end=datetime.utcnow() + timedelta(days=30)
            )
            db.add(subscription)
            db.flush()  # Get subscription.id
            
            # Link subscription to firm
            firm.subscription_id = subscription.id
        
        db.commit()
        db.refresh(firm)
        db.refresh(subscription)
        
        print(f"\n🎉 Successfully created subscription!")
        print(f"   Subscription ID: {subscription.id}")
        print(f"   Firm: {firm.firm_name}")
        print(f"   Plan: {subscription.plan_name}")
        print(f"   Seat Count: {subscription.seat_count}")
        print(f"   Monthly Price: ${subscription.monthly_price}")
        print(f"   Status: {subscription.status}")
        print(f"   Period: {subscription.current_period_start.date()} to {subscription.current_period_end.date()}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding subscription: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    firm_id = None
    if len(sys.argv) > 1:
        try:
            firm_id = UUID(sys.argv[1])
        except ValueError:
            print(f"❌ Invalid firm ID: {sys.argv[1]}")
            sys.exit(1)
    
    print("🌱 Seeding subscription...\n")
    seed_subscription(firm_id)
    print("\n✨ Done!")


"""
Script to fix userrole enum and stamp alembic version.
Run this from the backend directory with your virtual environment activated.
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

# Create database connection
engine = create_engine(DATABASE_URL)

print("Connecting to database...")
with engine.connect() as conn:
    # Start a transaction
    trans = conn.begin()
    
    try:
        # Add firm_admin to enum if it doesn't exist
        print("Adding 'firm_admin' to userrole enum...")
        conn.execute(text("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum 
                    WHERE enumlabel = 'firm_admin' 
                    AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
                ) THEN
                    ALTER TYPE userrole ADD VALUE 'firm_admin';
                END IF;
            END $$;
        """))
        
        # Add firm_advisor to enum if it doesn't exist
        print("Adding 'firm_advisor' to userrole enum...")
        conn.execute(text("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum 
                    WHERE enumlabel = 'firm_advisor' 
                    AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
                ) THEN
                    ALTER TYPE userrole ADD VALUE 'firm_advisor';
                END IF;
            END $$;
        """))
        
        # Stamp alembic version to the latest known migration
        print("Stamping alembic version to 6d6185e73276...")
        conn.execute(text("""
            UPDATE alembic_version 
            SET version_num = '6d6185e73276'
            WHERE version_num = '7a0c72f39586' OR version_num NOT IN (
                'ec0b9b4c6fec', '4ff8aece5340', '79dc61b1e153', '6d6185e73276'
            );
        """))
        
        # If no row exists, insert one
        conn.execute(text("""
            INSERT INTO alembic_version (version_num)
            SELECT '6d6185e73276'
            WHERE NOT EXISTS (SELECT 1 FROM alembic_version);
        """))
        
        trans.commit()
        print("✅ Successfully added enum values and fixed alembic version!")
        print("You can now run: alembic upgrade head")
        
    except Exception as e:
        trans.rollback()
        print(f"❌ Error: {e}")
        sys.exit(1)


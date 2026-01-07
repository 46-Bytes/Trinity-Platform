"""
Quick fix script to add hashed_password column to users table.
Run this directly: python fix_hashed_password.py
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Check if column exists
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'hashed_password'
    """))
    
    if result.fetchone():
        print("✅ hashed_password column already exists")
    else:
        print("➕ Adding hashed_password column...")
        conn.execute(text("""
            ALTER TABLE users 
            ADD COLUMN hashed_password VARCHAR(255) NULL
        """))
        conn.execute(text("""
            COMMENT ON COLUMN users.hashed_password IS 'Hashed password for email/password authentication'
        """))
        
        # Make auth0_id nullable if it's not already
        try:
            conn.execute(text("""
                ALTER TABLE users 
                ALTER COLUMN auth0_id DROP NOT NULL
            """))
            print("✅ Made auth0_id nullable")
        except Exception as e:
            print(f"⚠️  Could not make auth0_id nullable (might already be nullable): {e}")
        
        conn.execute(text("""
            COMMENT ON COLUMN users.auth0_id IS 'Auth0 user ID (sub claim from token). NULL for email/password users.'
        """))
        
        conn.commit()
        print("✅ Successfully added hashed_password column!")

print("✅ Done! You can now restart your backend server.")


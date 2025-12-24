-- Fix userrole enum by adding firm_admin and firm_advisor
-- Run this SQL directly in your PostgreSQL database

-- Add firm_admin to userrole enum (if not exists)
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

-- Add firm_advisor to userrole enum (if not exists)
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


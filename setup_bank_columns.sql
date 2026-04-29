-- Add bank details columns to students table if they don't exist
ALTER TABLE students ADD COLUMN IF NOT EXISTS bank_name VARCHAR(100);
ALTER TABLE students ADD COLUMN IF NOT EXISTS account_holder_name VARCHAR(100);
ALTER TABLE students ADD COLUMN IF NOT EXISTS account_number VARCHAR(50);
ALTER TABLE students ADD COLUMN IF NOT EXISTS ifsc_code VARCHAR(20);
ALTER TABLE students ADD COLUMN IF NOT EXISTS account_type ENUM('savings', 'current') DEFAULT 'savings';

-- Check if columns were added
DESCRIBE students;
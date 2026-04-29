#!/usr/bin/env python3
"""
Setup documents table and add documents_uploaded column to applications
"""
import mysql.connector
from mysql.connector import Error

def setup_documents():
    """Create documents table for document verification workflow"""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='Mi123456#',
            database='subsitech'
        )
        cursor = connection.cursor()
        
        # Create documents table
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS documents (
            id INT AUTO_INCREMENT PRIMARY KEY,
            application_id INT NOT NULL,
            document_type VARCHAR(100) NOT NULL,
            filename VARCHAR(255) NOT NULL,
            filepath VARCHAR(500) NOT NULL,
            file_size INT,
            verification_status ENUM('pending', 'verified', 'rejected') DEFAULT 'pending',
            rejection_reason TEXT,
            verified_by INT,
            verified_at TIMESTAMP NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
            FOREIGN KEY (verified_by) REFERENCES users(id) ON DELETE SET NULL,
            INDEX idx_application (application_id),
            INDEX idx_status (verification_status)
        )
        """
        
        cursor.execute(create_table_sql)
        print("✅ Documents table created successfully")
        
        # Add documents_uploaded column if it doesn't exist
        try:
            check_column_sql = """
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'applications' AND COLUMN_NAME = 'documents_uploaded'
            """
            cursor.execute(check_column_sql)
            if not cursor.fetchone():
                alter_table_sql = """
                ALTER TABLE applications 
                ADD COLUMN documents_uploaded BOOLEAN DEFAULT FALSE
                """
                cursor.execute(alter_table_sql)
                print("✅ documents_uploaded column added to applications table")
            else:
                print("✅ documents_uploaded column already exists")
        except Error as e:
            print(f"⚠️ Could not add column: {e}")
        
        connection.commit()
        cursor.close()
        connection.close()
        print("\n✅ Document verification setup complete!")
        
    except Error as err:
        print(f"❌ Error: {err}")
        return False
    
    return True

if __name__ == '__main__':
    setup_documents()

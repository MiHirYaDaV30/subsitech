#!/usr/bin/env python3
"""
Test document upload during application submission
"""
import mysql.connector
from datetime import datetime
import os

def test_application_with_documents():
    """Test that applications can be submitted with documents"""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='Mi123456#',
            database='subsitech'
        )
        cursor = connection.cursor(dictionary=True)
        
        print("🧪 Testing Application Submission with Documents...\n")
        
        # Check if documents table exists
        cursor.execute("SHOW TABLES LIKE 'documents'")
        if not cursor.fetchone():
            print("❌ Documents table not found")
            return False
        
        # Check if applications.documents_uploaded column exists
        cursor.execute("""
            SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_NAME = 'applications' AND COLUMN_NAME = 'documents_uploaded'
        """)
        if not cursor.fetchone():
            print("❌ documents_uploaded column not found")
            return False
        
        # Get a test student and scheme that haven't been paired yet
        # Try different combinations until we find one that works
        test_combinations = [
            (1, 3),  # student 1, scheme 3
            (1, 4),  # student 1, scheme 4
            (2, 1),  # student 2, scheme 1
            (2, 2),  # student 2, scheme 2
            (2, 3),  # student 2, scheme 3
            (3, 1),  # student 3, scheme 1
            (3, 2),  # student 3, scheme 2
            (3, 3),  # student 3, scheme 3
            (3, 4),  # student 3, scheme 4
        ]
        
        student_id = None
        scheme_id = None
        
        for s_id, sch_id in test_combinations:
            cursor.execute(
                "SELECT id FROM applications WHERE scheme_id = %s AND student_id = %s",
                (sch_id, s_id)
            )
            if not cursor.fetchone():
                student_id = s_id
                scheme_id = sch_id
                break
        
        if not student_id or not scheme_id:
            print("❌ Could not find a student/scheme combination that hasn't been applied to yet")
            return False
        
        # Simulate application submission with documents
        print("\n📝 Simulating application submission with documents...")
        
        # Insert test application
        cursor.execute(
            """
            INSERT INTO applications
            (scheme_id, student_id, status, statement_of_purpose, documents_uploaded)
            VALUES (%s, %s, 'submitted', %s, %s)
            """,
            (scheme_id, student_id, 'Test application with documents', True)
        )
        application_id = cursor.lastrowid
        
        # Insert test documents
        test_documents = [
            ('Income Certificate', 'income_cert.pdf', '/uploads/documents/test1.pdf', 1024000),
            ('ID Proof', 'aadhar_card.jpg', '/uploads/documents/test2.jpg', 512000),
            ('Academic Records', 'marksheet.pdf', '/uploads/documents/test3.pdf', 2048000)
        ]
        
        for doc_type, filename, filepath, file_size in test_documents:
            cursor.execute(
                """INSERT INTO documents (application_id, document_type, filename, filepath, file_size, verification_status)
                   VALUES (%s, %s, %s, %s, %s, 'pending')""",
                (application_id, doc_type, filename, filepath, file_size)
            )
        
        connection.commit()
        
        # Verify the application was created with documents_uploaded = TRUE
        cursor.execute(
            "SELECT id, documents_uploaded FROM applications WHERE id = %s",
            (application_id,)
        )
        app_result = cursor.fetchone()
        
        if app_result and app_result['documents_uploaded']:
            print("✅ Application created with documents_uploaded = TRUE")
        else:
            print("❌ Application documents_uploaded flag not set correctly")
            return False
        
        # Verify documents were created
        cursor.execute(
            "SELECT COUNT(*) as doc_count FROM documents WHERE application_id = %s",
            (application_id,)
        )
        doc_result = cursor.fetchone()
        
        if doc_result and doc_result['doc_count'] == 3:
            print("✅ 3 documents created successfully")
        else:
            print(f"❌ Expected 3 documents, found {doc_result['doc_count'] if doc_result else 0}")
            return False
        
        # Verify document details
        cursor.execute(
            "SELECT document_type, filename, verification_status FROM documents WHERE application_id = %s ORDER BY document_type",
            (application_id,)
        )
        docs = cursor.fetchall()
        
        expected_types = ['Academic Records', 'ID Proof', 'Income Certificate']
        actual_types = [doc['document_type'] for doc in docs]
        
        if actual_types == expected_types:
            print("✅ Document types match expected values")
        else:
            print(f"❌ Document types mismatch. Expected: {expected_types}, Got: {actual_types}")
            return False
        
        # Check all documents are pending verification
        pending_count = sum(1 for doc in docs if doc['verification_status'] == 'pending')
        if pending_count == 3:
            print("✅ All documents have pending verification status")
        else:
            print(f"❌ Expected 3 pending documents, found {pending_count}")
            return False
        
        print("\n✅ Application submission with documents test PASSED!")
        print("\n📋 Test Results:")
        print(f"   Application ID: {application_id}")
        print(f"   Documents uploaded: {len(docs)}")
        print(f"   All documents pending verification: ✓")
        print(f"   Application documents_uploaded flag: ✓")
        
        # Clean up test data
        print("\n🧹 Cleaning up test data...")
        cursor.execute("DELETE FROM documents WHERE application_id = %s", (application_id,))
        cursor.execute("DELETE FROM applications WHERE id = %s", (application_id,))
        connection.commit()
        print("✅ Test data cleaned up")
        
        cursor.close()
        connection.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

if __name__ == '__main__':
    test_application_with_documents()
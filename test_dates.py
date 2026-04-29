#!/usr/bin/env python3
import mysql.connector
from app import app, get_db, fetch_all, get_student_profile

# Test the student profile and applications
try:
    with app.app_context():
        print("Testing student profile for user_id=1:")
        student = get_student_profile(1)
        print(f"Student: {student}")
        if student:
            print(f"Student ID: {student.get('id')}")
            print(f"Student ID type: {type(student.get('id'))}")
        else:
            print("No student found for user_id=1")
        
        print("\nTesting get_student_applications:")
        from app import get_student_applications
        apps = get_student_applications(1)
        print(f"Applications: {apps}")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

import mysql.connector as mysql

print("Testing bank details saving functionality...")

conn = mysql.connect(host='localhost', user='root', password='Mi123456#', database='subsitech')
cursor = conn.cursor(dictionary=True)

# Check if a student has bank details
cursor.execute('''
    SELECT id, full_name, bank_name, account_holder_name, account_number, ifsc_code, account_type
    FROM students
    LIMIT 3
''')
students = cursor.fetchall()

print("\nCurrent students with bank details:")
for student in students:
    bank_status = "✅ Has bank details" if student['bank_name'] else "❌ No bank details"
    print(f"  Student: {student['full_name']} - {bank_status}")
    if student['bank_name']:
        print(f"    Bank: {student['bank_name']}")
        print(f"    Account: {student['account_number']}")

# Test updating bank details for a student
print("\n📝 Testing bank details update...")
test_student_id = 1
cursor.execute('''
    UPDATE students 
    SET bank_name = 'Test Bank',
        account_holder_name = 'Test User',
        account_number = '1234567890',
        ifsc_code = 'TEST0001234',
        account_type = 'savings'
    WHERE id = %s
''', (test_student_id,))
conn.commit()

# Verify the update
cursor.execute('''
    SELECT bank_name, account_holder_name, account_number, ifsc_code, account_type
    FROM students
    WHERE id = %s
''', (test_student_id,))
result = cursor.fetchone()
if result:
    print(f"✅ Bank details saved successfully!")
    print(f"   Bank: {result['bank_name']}")
    print(f"   Account Holder: {result['account_holder_name']}")
    print(f"   Account Number: {result['account_number']}")
    print(f"   IFSC: {result['ifsc_code']}")
    print(f"   Type: {result['account_type']}")
else:
    print("❌ Failed to save bank details")

cursor.close()
conn.close()

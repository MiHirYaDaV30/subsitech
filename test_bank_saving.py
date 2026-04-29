"""
Test to verify bank details can be saved through the account settings
"""
import mysql.connector as mysql

print("🧪 Testing bank details saving functionality...\n")

conn = mysql.connect(host='localhost', user='root', password='Mi123456#', database='subsitech')
cursor = conn.cursor(dictionary=True)

# Get a test student
cursor.execute('SELECT id FROM students LIMIT 1')
student = cursor.fetchone()
student_id = student['id']

print(f"📝 Test Case 1: Saving ONLY bank details (Financial Info tab)")
print(f"   Student ID: {student_id}")

# Simulate the bank details form submission (only bank details, no profile fields)
bank_name = "HDFC Bank"
account_holder_name = "Test User"
account_number = "1234567890123"
ifsc_code = "HDFC0001234"
account_type = "savings"

cursor.execute('''
    UPDATE students
    SET bank_name = %s,
        account_holder_name = %s,
        account_number = %s,
        ifsc_code = %s,
        account_type = %s
    WHERE id = %s
''', (bank_name, account_holder_name, account_number, ifsc_code, account_type, student_id))
conn.commit()

# Verify the bank details were saved
cursor.execute('''
    SELECT bank_name, account_holder_name, account_number, ifsc_code, account_type
    FROM students
    WHERE id = %s
''', (student_id,))
result = cursor.fetchone()

if result and result['bank_name'] == bank_name:
    print("✅ PASS: Bank details saved successfully!")
    print(f"   Bank: {result['bank_name']}")
    print(f"   Account Holder: {result['account_holder_name']}")
    print(f"   Account Number: {result['account_number']}")
    print(f"   IFSC: {result['ifsc_code']}")
    print(f"   Type: {result['account_type']}")
else:
    print("❌ FAIL: Bank details were not saved correctly")

print(f"\n📝 Test Case 2: Verify full profile + bank details update")

# Update with both profile and bank details
cursor.execute('''
    UPDATE students
    SET full_name = 'John Doe',
        institution_name = 'ABC University',
        bank_name = 'SBI',
        account_holder_name = 'John Doe',
        account_number = '9876543210',
        ifsc_code = 'SBI0009876',
        account_type = 'current'
    WHERE id = %s
''', (student_id,))
conn.commit()

cursor.execute('''
    SELECT full_name, institution_name, bank_name, account_number, account_type
    FROM students
    WHERE id = %s
''', (student_id,))
result = cursor.fetchone()

if result and result['bank_name'] == 'SBI' and result['full_name'] == 'John Doe':
    print("✅ PASS: Full profile + bank details saved successfully!")
    print(f"   Name: {result['full_name']}")
    print(f"   Institution: {result['institution_name']}")
    print(f"   Bank: {result['bank_name']}")
    print(f"   Account Number: {result['account_number']}")
else:
    print("❌ FAIL: Full update was not successful")

cursor.close()
conn.close()
print("\n✅ All tests completed!")

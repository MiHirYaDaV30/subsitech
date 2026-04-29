import mysql.connector as mysql

print('Testing application auto-update functionality...')

conn = mysql.connect(host='localhost', user='root', password='Mi123456#', database='subsitech')
cursor = conn.cursor(dictionary=True)

# Check current application statuses
cursor.execute("SELECT id, student_id, status FROM applications WHERE status IN ('approved', 'completed') LIMIT 5")
apps = cursor.fetchall()
print(f'Found {len(apps)} approved/completed applications:')
for app in apps:
    print(f'  App ID {app["id"]}: Status = {app["status"]}')

# Check if any students have bank details
cursor.execute("SELECT id, user_id, account_number FROM students WHERE account_number IS NOT NULL LIMIT 3")
students_with_bank = cursor.fetchall()
print(f'Found {len(students_with_bank)} students with bank details:')
for student in students_with_bank:
    print(f'  Student ID {student["id"]}: Account {student["account_number"][-4:]}****')

cursor.close()
conn.close()
print('Database check complete!')
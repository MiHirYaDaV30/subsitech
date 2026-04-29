import mysql.connector as mysql

conn = mysql.connect(host='localhost', user='root', password='Mi123456#', database='subsitech')
cursor = conn.cursor(dictionary=True)

# Check current application statuses
cursor.execute('SELECT id, status FROM applications LIMIT 10')
apps = cursor.fetchall()
print('Current applications:')
for app in apps:
    print(f'  App {app["id"]}: {app["status"]}')

# Test the new query logic - should only show submitted and in_review
cursor.execute('''
    SELECT a.id, a.status
    FROM applications a
    JOIN schemes s ON s.id = a.scheme_id
    WHERE s.donor_id = 1 AND a.status IN ("submitted", "in_review")
''')
review_apps = cursor.fetchall()
print(f'\nApplications that would appear in review portal: {len(review_apps)}')
for app in review_apps:
    print(f'  App {app["id"]}: {app["status"]}')

cursor.close()
conn.close()
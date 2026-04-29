import mysql.connector

conn = mysql.connector.connect(host='localhost', user='root', password='Mi123456#', database='subsitech')
cursor = conn.cursor(dictionary=True)

cursor.execute('SELECT COUNT(*) as count FROM applications')
result = cursor.fetchone()
print(f'Total applications: {result["count"]}')

cursor.execute('SELECT id, scheme_id, student_id FROM applications LIMIT 5')
apps = cursor.fetchall()
for app in apps:
    print(f'App {app["id"]}: Student {app["student_id"]} -> Scheme {app["scheme_id"]}')

cursor.close()
conn.close()
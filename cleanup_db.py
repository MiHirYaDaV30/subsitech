import mysql.connector as mysql

print('🧹 Cleaning up unnecessary database tables...')

conn = mysql.connect(host='localhost', user='root', password='Mi123456#', database='subsitech')
cursor = conn.cursor()

# Tables to drop (unused and not referenced in code)
tables_to_drop = [
    'student_documents',  # 0 rows, not used
    'application_documents',  # 0 rows, not used
    'reviews',  # 0 rows, not used (application status handles reviews)
    'consultations'  # 0 rows, not used
]

for table in tables_to_drop:
    try:
        cursor.execute(f'DROP TABLE IF EXISTS {table}')
        print(f'✅ Dropped table: {table}')
    except Exception as e:
        print(f'❌ Error dropping {table}: {e}')

conn.commit()
cursor.close()
conn.close()

print('🎉 Database cleanup completed!')
print('Removed 4 unnecessary tables that had 0 rows and were not used in the application.')
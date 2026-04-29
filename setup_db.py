import mysql.connector as mysql

# Connect to database
conn = mysql.connect(host='localhost', user='root', password='Mi123456#', database='subsitech')
cursor = conn.cursor()

# Check current columns
cursor.execute('DESCRIBE students')
columns = [col[0] for col in cursor.fetchall()]
print('Current students table columns:', columns)

# Check which bank columns are missing
bank_cols = ['bank_name', 'account_holder_name', 'account_number', 'ifsc_code', 'account_type']
missing = [col for col in bank_cols if col not in columns]

if missing:
    print('Missing bank columns:', missing)
    for col in missing:
        if col == 'account_type':
            cursor.execute("ALTER TABLE students ADD COLUMN account_type ENUM('savings', 'current') DEFAULT 'savings'")
        else:
            cursor.execute(f"ALTER TABLE students ADD COLUMN {col} VARCHAR(100)")
        print(f'Added: {col}')
    conn.commit()
else:
    print('All bank columns exist!')

# Check notifications
cursor.execute('SELECT COUNT(*) FROM notifications')
count = cursor.fetchone()[0]
print(f'Notifications in database: {count}')

cursor.close()
conn.close()
print('Setup complete!')
import mysql.connector
import os

def seed_database():
    print("Connecting to MySQL...")
    try:
        # Connect to MySQL server
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='Mi123456#'
        )
        cursor = connection.cursor()
        
        # Read the SQL file
        sql_file_path = os.path.join(os.path.expanduser('~'), '.gemini', 'antigravity', 'brain', '967969c7-914c-4cf4-b14c-d600226ff360', 'dummy_data.sql')
        
        print(f"Reading SQL file from {sql_file_path}...")
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
            
        print("Executing SQL script (this will create subsitech2 and insert 100+ rows)...")
        
        # Execute the script (split by statements)
        # multi=True allows executing multiple statements in one call
        results = cursor.execute(sql_script, multi=True)
        
        for result in results:
            pass # Iterate through results to ensure execution
            
        connection.commit()
        print("\n✅ Success! All dummy data has been successfully inputted into the database.")
        
    except FileNotFoundError:
        print(f"❌ Error: Could not find the dummy_data.sql file at {sql_file_path}")
    except mysql.connector.Error as err:
        print(f"❌ MySQL Error: {err}")
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'connection' in locals() and connection.is_connected():
            connection.close()

if __name__ == "__main__":
    seed_database()

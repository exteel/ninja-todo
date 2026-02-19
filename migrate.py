import sqlite3

db = sqlite3.connect('todo.db')

# Add is_admin column if not exists
columns = [c[1] for c in db.execute('PRAGMA table_info(users)').fetchall()]
if 'is_admin' not in columns:
    db.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0')
    print('Added is_admin column')
else:
    print('Column already exists')

# Set VE4SRCD6 as admin
db.execute("UPDATE users SET is_admin=1 WHERE code='VE4SRCD6'")
db.commit()

# Show all users
rows = db.execute('SELECT code, name, is_admin FROM users').fetchall()
print('\nUsers:')
for r in rows:
    print(f'  code={r[0]}  name={r[1]}  admin={r[2]}')

db.close()
print('\nDone!')

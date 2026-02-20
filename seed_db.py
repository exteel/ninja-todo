import sqlite3
import os

DATABASE = os.environ.get('DATABASE_PATH', 'todo.db')

users = [
    (1, 'VE4SRCD6', 'Віталій', 1, '2026-02-19T22:37:30.894267'),
    (2, '9WH9FKDN', 'Юля', 0, '2026-02-20T00:37:31.055209'),
]

db = sqlite3.connect(DATABASE)

# Ensure is_admin column exists
try:
    db.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0')
except:
    pass

for user in users:
    existing = db.execute('SELECT id FROM users WHERE code = ?', (user[1],)).fetchone()
    if not existing:
        db.execute(
            'INSERT INTO users (id, code, name, is_admin, created_at) VALUES (?, ?, ?, ?, ?)',
            user
        )
        print(f'Created user: {user[2]} ({user[1]})')
    else:
        db.execute('UPDATE users SET is_admin = ? WHERE code = ?', (user[3], user[1]))
        print(f'Updated user: {user[2]} ({user[1]})')

db.commit()
db.close()
print('Done!')

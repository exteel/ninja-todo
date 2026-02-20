import sqlite3, os

DATABASE = os.path.join(os.path.expanduser('~'), 'ninja-todo', 'todo.db')
db = sqlite3.connect(DATABASE)

# Add position to todos
try:
    db.execute('ALTER TABLE todos ADD COLUMN position INTEGER DEFAULT 0')
    print('Added position column')
except: print('position exists')

# Create subtasks table
db.execute('''
    CREATE TABLE IF NOT EXISTS subtasks (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        todo_id    INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
        text       TEXT NOT NULL,
        done       INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )
''')
db.execute('CREATE INDEX IF NOT EXISTS idx_subtasks_todo ON subtasks(todo_id)')

# Set initial positions
db.execute('''
    UPDATE todos SET position = id WHERE position = 0 OR position IS NULL
''')

db.commit()
db.close()
print('Migration done!')

path = '/Users/vitaliikovalchuk/ninja-todo/app.py'
with open(path, 'r') as f:
    content = f.read()

old = "        CREATE INDEX IF NOT EXISTS idx_todos_done ON todos(user_id, done);
    """)"""
new = "        CREATE INDEX IF NOT EXISTS idx_todos_done ON todos(user_id, done);

        CREATE TABLE IF NOT EXISTS subtasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            todo_id    INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
            text       TEXT NOT NULL,
            done       INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_subtasks_todo ON subtasks(todo_id);
    """)"""

content = content.replace(old, new)

with open(path, 'w') as f:
    f.write(content)
print('init_db patched!')

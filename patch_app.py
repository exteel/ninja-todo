path = '/Users/vitaliikovalchuk/ninja-todo/app.py'
with open(path, 'r') as f:
    content = f.read()

# 1. Fix ORDER_SQL to use position
content = content.replace(
    'ORDER_SQL = " ORDER BY done ASC, CASE rank WHEN \'S\' THEN 0 WHEN \'A\' THEN 1 WHEN \'B\' THEN 2 WHEN \'C\' THEN 3 ELSE 4 END, created_at DESC"',
    'ORDER_SQL = " ORDER BY done ASC, position ASC, created_at DESC"'
)

# 2. Add new APIs before the seed comment
new_apis = """
# --- API: Reorder ---
@app.route("/api/reorder", methods=["POST"])
@login_required
def api_reorder():
    user_id = get_user_id()
    items = request.get_json(silent=True) or []
    db = get_db()
    for item in items:
        db.execute("UPDATE todos SET position=? WHERE id=? AND user_id=?",
                   (item['position'], item['id'], user_id))
    db.commit()
    return jsonify({"ok": True})

# --- API: Get Subtasks ---
@app.route("/api/subtasks/<int:todo_id>")
@login_required
def api_get_subtasks(todo_id):
    user_id = get_user_id()
    db = get_db()
    get_todo_or_404(db, todo_id, user_id)
    rows = db.execute("SELECT * FROM subtasks WHERE todo_id=? ORDER BY created_at ASC", (todo_id,)).fetchall()
    return jsonify([dict(r) for r in rows])

# --- API: Add Subtask ---
@app.route("/api/subtasks/<int:todo_id>/add", methods=["POST"])
@login_required
def api_add_subtask(todo_id):
    user_id = get_user_id()
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Текст не може бути порожнім"}), 400
    if len(text) > 200:
        return jsonify({"error": "Максимум 200 символів"}), 400
    db = get_db()
    get_todo_or_404(db, todo_id, user_id)
    cur = db.execute("INSERT INTO subtasks (todo_id, text, done, created_at) VALUES (?, ?, 0, ?)",
                     (todo_id, text, datetime.now().isoformat()))
    db.commit()
    row = db.execute("SELECT * FROM subtasks WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201

# --- API: Toggle Subtask ---
@app.route("/api/subtasks/toggle/<int:sub_id>", methods=["POST"])
@login_required
def api_toggle_subtask(sub_id):
    user_id = get_user_id()
    db = get_db()
    sub = db.execute("SELECT * FROM subtasks WHERE id=?", (sub_id,)).fetchone()
    if not sub:
        return jsonify({"error": "Не знайдено"}), 404
    get_todo_or_404(db, sub['todo_id'], user_id)
    new_done = 0 if sub['done'] else 1
    db.execute("UPDATE subtasks SET done=? WHERE id=?", (new_done, sub_id))
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM subtasks WHERE id=?", (sub_id,)).fetchone()))

# --- API: Delete Subtask ---
@app.route("/api/subtasks/delete/<int:sub_id>", methods=["DELETE"])
@login_required
def api_delete_subtask(sub_id):
    user_id = get_user_id()
    db = get_db()
    sub = db.execute("SELECT * FROM subtasks WHERE id=?", (sub_id,)).fetchone()
    if not sub:
        return jsonify({"error": "Не знайдено"}), 404
    get_todo_or_404(db, sub['todo_id'], user_id)
    db.execute("DELETE FROM subtasks WHERE id=?", (sub_id,))
    db.commit()
    return jsonify({"ok": True})
"""

content = content.replace(
    '# Завжди ініціалізуємо БД при старті',
    new_apis + '\n# Завжди ініціалізуємо БД при старті'
)

with open(path, 'w') as f:
    f.write(content)
print('Done!')

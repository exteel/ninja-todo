import sqlite3
import os
import secrets
import string
from datetime import datetime, date
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, jsonify, g, session, abort
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "naruto-ninja-super-secret-2024")
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "todo.db")

RANKS = ["D", "C", "B", "A", "S"]
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "hokage2024")


# ─── Database helpers ───────────────────────────────────────────────
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            code       TEXT    NOT NULL UNIQUE,
            name       TEXT    NOT NULL DEFAULT 'Ніндзя',
            created_at TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS todos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            text        TEXT    NOT NULL,
            done        INTEGER NOT NULL DEFAULT 0,
            rank        TEXT    NOT NULL DEFAULT 'D',
            deadline    TEXT,
            created_at  TEXT    NOT NULL,
            done_at     TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_todos_user ON todos(user_id);
        CREATE INDEX IF NOT EXISTS idx_todos_done ON todos(user_id, done);

        CREATE TABLE IF NOT EXISTS subtasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            todo_id    INTEGER NOT NULL REFERENCES todos(id) ON DELETE CASCADE,
            text       TEXT NOT NULL,
            done       INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_subtasks_todo ON subtasks(todo_id);
    """)
    db.commit()
    db.close()


def row_to_dict(row):
    d = dict(row)
    d["done"] = bool(d["done"])
    return d


def get_stats(db, user_id):
    row = db.execute("""
        SELECT
            COUNT(*) as total,
            SUM(done) as done
        FROM todos WHERE user_id = ?
    """, (user_id,)).fetchone()
    total = row["total"] or 0
    done  = row["done"]  or 0
    return {"total": total, "done": done, "pending": total - done}


def ninja_rank(done_count):
    if done_count >= 10:
        return ("🔴", "Хокаге")
    elif done_count >= 7:
        return ("🟡", "Джонін")
    elif done_count >= 4:
        return ("🟢", "Чунін")
    elif done_count >= 1:
        return ("🔵", "Генін")
    return ("⚪", "Академія")


def generate_code(length=8):
    """Генерує читабельний invite-код."""
    alphabet = string.ascii_uppercase + string.digits
    # Remove confusable chars
    alphabet = alphabet.translate(str.maketrans('', '', 'O0I1L'))
    return ''.join(secrets.choice(alphabet) for _ in range(length))


# ─── Auth helpers ────────────────────────────────────────────────────
def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["is_admin"] = bool(d.get("is_admin", 0))
    return d


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def get_user_id():
    return session["user_id"]


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ─── Auth routes ────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        if not code:
            error = "Введіть код доступу"
        else:
            db = get_db()
            user = db.execute("SELECT * FROM users WHERE code = ?", (code,)).fetchone()
            if user:
                session["user_id"] = user["id"]
                session.permanent = True
                return redirect(url_for("index"))
            else:
                error = "Невірний код. Перевірте і спробуйте знову."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─── Admin routes ───────────────────────────────────────────────────
@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_panel"))
    error = None
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_panel"))
        error = "Невірний пароль"
    return render_template("admin_login.html", error=error)


@app.route("/admin/panel")
@admin_required
def admin_panel():
    db = get_db()
    rows = db.execute("""
        SELECT u.id, u.code, u.name, u.created_at,
               COUNT(t.id) as total_todos,
               COALESCE(SUM(t.done), 0) as done_todos
        FROM users u
        LEFT JOIN todos t ON t.user_id = u.id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """).fetchall()
    users = []
    for u in rows:
        d = dict(u)
        d['done_todos'] = int(d['done_todos'] or 0)
        d['total_todos'] = int(d['total_todos'] or 0)
        users.append(d)
    return render_template("admin_panel.html", users=users)


@app.route("/admin/create", methods=["POST"])
@admin_required
def admin_create():
    name = request.form.get("name", "").strip() or "Ніндзя"
    db = get_db()
    for _ in range(10):
        code = generate_code()
        if not db.execute("SELECT id FROM users WHERE code=?", (code,)).fetchone():
            break
    db.execute(
        "INSERT INTO users (code, name, created_at) VALUES (?, ?, ?)",
        (code, name, datetime.now().isoformat())
    )
    db.commit()
    return redirect(url_for("admin_panel"))


@app.route("/admin/delete-user/<int:user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    db = get_db()
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
    return redirect(url_for("admin_panel"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


# ─── Page route ─────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    """Головна сторінка."""
    user_id = get_user_id()
    filter_by = request.args.get("filter", "all")
    search = request.args.get("search", "").strip()

    db = get_db()
    conditions = ["user_id = ?"]
    params = [user_id]

    if filter_by == "active":
        conditions.append("done = 0")
    elif filter_by == "done":
        conditions.append("done = 1")

    if search:
        conditions.append("text LIKE ?")
        params.append(f"%{search}%")

    query = "SELECT * FROM todos WHERE " + " AND ".join(conditions)
    query += " ORDER BY done ASC, CASE rank WHEN 'S' THEN 0 WHEN 'A' THEN 1 WHEN 'B' THEN 2 WHEN 'C' THEN 3 ELSE 4 END, created_at DESC"

    rows = db.execute(query, params).fetchall()
    todos = [row_to_dict(r) for r in rows]

    stats = get_stats(db, user_id)
    rank_icon, rank_name = ninja_rank(stats["done"])
    user = current_user()
    today = date.today().isoformat()

    return render_template(
        "index.html",
        todos=todos,
        stats=stats,
        rank_icon=rank_icon,
        rank_name=rank_name,
        current_filter=filter_by,
        search=search,
        ranks=RANKS,
        today=today,
        user=user,
    )


# ─── API helpers ────────────────────────────────────────────────────
ORDER_SQL = " ORDER BY done ASC, position ASC, created_at DESC"


def get_todo_or_404(db, todo_id, user_id):
    row = db.execute(
        "SELECT * FROM todos WHERE id = ? AND user_id = ?",
        (todo_id, user_id)
    ).fetchone()
    if not row:
        abort(404)
    return row


# ─── API: Add ───────────────────────────────────────────────────────
@app.route("/api/add", methods=["POST"])
@login_required
def api_add():
    user_id = get_user_id()
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    rank = data.get("rank", "D").upper()
    deadline = data.get("deadline") or None

    if not text:
        return jsonify({"error": "Текст місії не може бути порожнім"}), 400
    if len(text) > 200:
        return jsonify({"error": "Максимум 200 символів"}), 400
    if rank not in RANKS:
        rank = "D"

    db = get_db()
    cur = db.execute(
        "INSERT INTO todos (user_id, text, rank, deadline, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, text, rank, deadline, datetime.now().isoformat()),
    )
    db.commit()
    row = db.execute("SELECT * FROM todos WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(row)), 201


# ─── API: Toggle ────────────────────────────────────────────────────
@app.route("/api/toggle/<int:todo_id>", methods=["POST"])
@login_required
def api_toggle(todo_id):
    user_id = get_user_id()
    db = get_db()
    row = get_todo_or_404(db, todo_id, user_id)
    new_done = 0 if row["done"] else 1
    done_at = datetime.now().isoformat() if new_done else None
    db.execute("UPDATE todos SET done=?, done_at=? WHERE id=?", (new_done, done_at, todo_id))
    db.commit()
    return jsonify(row_to_dict(db.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()))


# ─── API: Delete ────────────────────────────────────────────────────
@app.route("/api/delete/<int:todo_id>", methods=["DELETE"])
@login_required
def api_delete(todo_id):
    user_id = get_user_id()
    db = get_db()
    row = get_todo_or_404(db, todo_id, user_id)
    db.execute("DELETE FROM todos WHERE id=?", (todo_id,))
    db.commit()
    return jsonify({"ok": True, "deleted": row_to_dict(row)})


# ─── API: Edit ──────────────────────────────────────────────────────
@app.route("/api/edit/<int:todo_id>", methods=["PUT"])
@login_required
def api_edit(todo_id):
    user_id = get_user_id()
    data = request.get_json(silent=True) or {}
    db = get_db()
    row = get_todo_or_404(db, todo_id, user_id)

    text = data.get("text", "").strip()
    rank = data.get("rank", row["rank"]).upper()
    deadline = data.get("deadline", row["deadline"]) or None

    if not text:
        return jsonify({"error": "Текст не може бути порожнім"}), 400
    if len(text) > 200:
        return jsonify({"error": "Максимум 200 символів"}), 400
    if rank not in RANKS:
        rank = row["rank"]

    db.execute(
        "UPDATE todos SET text=?, rank=?, deadline=? WHERE id=?",
        (text, rank, deadline, todo_id),
    )
    db.commit()
    return jsonify(row_to_dict(db.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()))


# ─── API: Stats ─────────────────────────────────────────────────────
@app.route("/api/stats")
@login_required
def api_stats():
    user_id = get_user_id()
    db = get_db()
    stats = get_stats(db, user_id)
    icon, name = ninja_rank(stats["done"])
    stats["rank_icon"] = icon
    stats["rank_name"] = name
    stats["chakra"] = round((stats["done"] / stats["total"] * 100) if stats["total"] > 0 else 0)
    return jsonify(stats)


# ─── API: List ──────────────────────────────────────────────────────
@app.route("/api/todos")
@login_required
def api_todos():
    user_id = get_user_id()
    filter_by = request.args.get("filter", "all")
    search = request.args.get("search", "").strip()

    db = get_db()
    conditions = ["user_id = ?"]
    params = [user_id]

    if filter_by == "active":
        conditions.append("done = 0")
    elif filter_by == "done":
        conditions.append("done = 1")
    if search:
        conditions.append("text LIKE ?")
        params.append(f"%{search}%")

    rows = db.execute(
        "SELECT * FROM todos WHERE " + " AND ".join(conditions) + ORDER_SQL,
        params
    ).fetchall()
    return jsonify([row_to_dict(r) for r in rows])



# --- API: Reorder ---
@app.route("/api/reorder", methods=["POST"])
@login_required
def api_reorder():
    user_id = get_user_id()
    items = request.get_json(silent=True) or []
    db = get_db()
    for item in items:
        db.execute("UPDATE todos SET position=? WHERE id=? AND user_id=?",
                   (item["position"], item["id"], user_id))
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/subtasks/<int:todo_id>")
@login_required
def api_get_subtasks(todo_id):
    user_id = get_user_id()
    db = get_db()
    get_todo_or_404(db, todo_id, user_id)
    rows = db.execute(
        "SELECT * FROM subtasks WHERE todo_id=? ORDER BY created_at ASC",
        (todo_id,)
    ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/subtasks/<int:todo_id>/add", methods=["POST"])
@login_required
def api_add_subtask(todo_id):
    user_id = get_user_id()
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Текст не може бути порожнім"}), 400
    db = get_db()
    get_todo_or_404(db, todo_id, user_id)
    cur = db.execute(
        "INSERT INTO subtasks (todo_id, text, done, created_at) VALUES (?, ?, 0, ?)",
        (todo_id, text, datetime.now().isoformat())
    )
    db.commit()
    row = db.execute("SELECT * FROM subtasks WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@app.route("/api/subtasks/toggle/<int:sub_id>", methods=["POST"])
@login_required
def api_toggle_subtask(sub_id):
    user_id = get_user_id()
    db = get_db()
    sub = db.execute("SELECT * FROM subtasks WHERE id=?", (sub_id,)).fetchone()
    if not sub:
        return jsonify({"error": "Не знайдено"}), 404
    get_todo_or_404(db, sub["todo_id"], user_id)
    new_done = 0 if sub["done"] else 1
    db.execute("UPDATE subtasks SET done=? WHERE id=?", (new_done, sub_id))
    db.commit()
    return jsonify(dict(db.execute("SELECT * FROM subtasks WHERE id=?", (sub_id,)).fetchone()))


@app.route("/api/subtasks/delete/<int:sub_id>", methods=["DELETE"])
@login_required
def api_delete_subtask(sub_id):
    user_id = get_user_id()
    db = get_db()
    sub = db.execute("SELECT * FROM subtasks WHERE id=?", (sub_id,)).fetchone()
    if not sub:
        return jsonify({"error": "Не знайдено"}), 404
    get_todo_or_404(db, sub["todo_id"], user_id)
    db.execute("DELETE FROM subtasks WHERE id=?", (sub_id,))
    db.commit()
    return jsonify({"ok": True})

with app.app_context():
    init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
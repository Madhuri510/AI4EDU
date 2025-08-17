# utils/conversation_store.py
import os, sqlite3, json, datetime
from typing import List, Optional, Dict, Any

_DB_PATH = os.path.join(os.getcwd(), "casebuilder_history.db")

def _conn():
    cx = sqlite3.connect(_DB_PATH, check_same_thread=False)
    cx.execute("PRAGMA foreign_keys = ON;")   # make cascade deletes work
    return cx


def init_db():
    with _conn() as cx:
        cx.execute("""
        CREATE TABLE IF NOT EXISTS sessions(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          title TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """)
        cx.execute("""
        CREATE TABLE IF NOT EXISTS messages(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          session_id INTEGER NOT NULL,
          role TEXT NOT NULL,              -- "user" or "assistant"
          content TEXT NOT NULL,           -- raw text
          meta_json TEXT NOT NULL,         -- JSON (e.g., blob_path)
          created_at TEXT NOT NULL,
          FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );
        """)
        cx.commit()

def _now():
    return datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"

def create_session(title: Optional[str]=None) -> int:
    title = title.strip() if title else "Untitled"
    now = _now()
    with _conn() as cx:
        cur = cx.execute("INSERT INTO sessions(title,created_at,updated_at) VALUES(?,?,?)",
                         (title, now, now))
        cx.commit()
        return cur.lastrowid

def list_sessions(search: str="", limit: int=50) -> List[Dict[str, Any]]:
    q = "SELECT id, title, created_at, updated_at FROM sessions"
    args = []
    if search:
        q += " WHERE title LIKE ?"
        args.append(f"%{search}%")
    q += " ORDER BY updated_at DESC LIMIT ?"
    args.append(limit)
    with _conn() as cx:
        rows = cx.execute(q, args).fetchall()
    return [{"id": r[0], "title": r[1], "created_at": r[2], "updated_at": r[3]} for r in rows]

def get_session(session_id: int) -> Dict[str, Any]:
    with _conn() as cx:
        s = cx.execute("SELECT id, title, created_at, updated_at FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not s: return {}
        msgs = cx.execute("""SELECT role, content, meta_json, created_at
                             FROM messages WHERE session_id=? ORDER BY id ASC""", (session_id,)).fetchall()
    return {
        "id": s[0], "title": s[1], "created_at": s[2], "updated_at": s[3],
        "messages": [{"role": m[0], "content": m[1], "meta": json.loads(m[2]), "created_at": m[3]} for m in msgs]
    }

def add_message(session_id: int, role: str, content: str, meta: Optional[Dict[str, Any]]=None):
    meta = meta or {}
    now = _now()
    with _conn() as cx:
        cx.execute("""INSERT INTO messages(session_id, role, content, meta_json, created_at)
                      VALUES(?,?,?,?,?)""", (session_id, role, content, json.dumps(meta), now))
        cx.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
        cx.commit()

def rename_session(session_id: int, new_title: str):
    new_title = new_title.strip() or "Untitled"
    now = _now()
    with _conn() as cx:
        cx.execute("UPDATE sessions SET title=?, updated_at=? WHERE id=?", (new_title, now, session_id))
        cx.commit()

def delete_session(session_id: int):
    with _conn() as cx:
        cx.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        cx.execute("DELETE FROM sessions WHERE id=?", (session_id,))
        cx.commit()

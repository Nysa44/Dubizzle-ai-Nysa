
from __future__ import annotations

import csv
import json
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import settings


_lock = threading.Lock()


def conn() -> sqlite3.Connection:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(settings.database_path, check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    c = conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            min_budget REAL,
            max_budget REAL,
            preferences TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            active_listing_ids TEXT DEFAULT '[]',
            focused_listing_id INTEGER,
            last_intent TEXT DEFAULT '',
            pending_action TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS favorites (
            user_id TEXT NOT NULL,
            listing_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, listing_id)
        );
        CREATE TABLE IF NOT EXISTS bookings (
            booking_ref TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            listing_id INTEGER NOT NULL,
            appointment_at TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(listing_id, appointment_at)
        );
        """
    )
    # Lightweight migration for databases created by earlier project versions.
    try:
        c.execute("ALTER TABLE sessions ADD COLUMN focused_listing_id INTEGER")
        c.commit()
    except sqlite3.OperationalError:
        pass
    c.commit()
    c.close()


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_user(user_id: str, name: str | None = None) -> dict[str, Any]:
    c = conn()
    row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    ts = now()
    if row:
        if name and not row["name"]:
            c.execute("UPDATE users SET name=?, updated_at=? WHERE user_id=?", (name, ts, user_id))
            c.commit()
        result = dict(row)
    else:
        c.execute(
            "INSERT INTO users(user_id,name,created_at,updated_at) VALUES(?,?,?,?)",
            (user_id, name or user_id, ts, ts),
        )
        c.commit()
        result = dict(c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone())
    c.close()
    return result


def append_preference(user_id: str, preference: str, max_items: int = 8) -> None:
    """Append a durable user search/preference without overwriting prior memory."""
    pref = (preference or "").strip()
    if not pref:
        return
    profile = get_profile(user_id)
    raw = (profile.get("preferences") or "").strip()
    items = [x.strip() for x in raw.split(" | ") if x.strip()]
    items = [x for x in items if x.lower() != pref.lower()]
    items.append(pref)
    update_profile(user_id, preferences=" | ".join(items[-max_items:]))


def update_profile(user_id: str, **fields: Any) -> None:
    allowed = {"name", "min_budget", "max_budget", "preferences"}
    clean = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not clean:
        return
    clean["updated_at"] = now()
    assignments = ", ".join(f"{k}=?" for k in clean)
    values = list(clean.values()) + [user_id]
    c = conn()
    c.execute(f"UPDATE users SET {assignments} WHERE user_id=?", values)
    c.commit()
    c.close()


def get_profile(user_id: str) -> dict[str, Any]:
    c = conn()
    row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    c.close()
    if not row:
        return {"user_id": user_id}
    data = dict(row)
    return data


def get_or_create_session(user_id: str, session_id: str | None) -> str:
    sid = session_id or str(uuid.uuid4())
    c = conn()
    row = c.execute("SELECT session_id FROM sessions WHERE session_id=?", (sid,)).fetchone()
    if not row:
        c.execute(
            "INSERT INTO sessions(session_id,user_id,created_at,updated_at) VALUES(?,?,?,?)",
            (sid, user_id, now(), now()),
        )
        c.commit()
    c.close()
    return sid


def set_session_state(session_id: str, listing_ids: list[int], intent: str, focused_listing_id: int | None = None) -> None:
    c = conn()
    c.execute(
        "UPDATE sessions SET active_listing_ids=?, focused_listing_id=?, last_intent=?, updated_at=? WHERE session_id=?",
        (json.dumps(listing_ids), focused_listing_id, intent, now(), session_id),
    )
    c.commit()
    c.close()


def set_focused_listing(session_id: str, listing_id: int | None) -> None:
    c = conn()
    c.execute("UPDATE sessions SET focused_listing_id=?, updated_at=? WHERE session_id=?", (listing_id, now(), session_id))
    c.commit()
    c.close()


def get_session_state(session_id: str) -> dict[str, Any]:
    c = conn()
    row = c.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    c.close()
    if not row:
        return {"active_listing_ids": [], "focused_listing_id": None, "last_intent": ""}
    data = dict(row)
    try:
        data["active_listing_ids"] = json.loads(data.get("active_listing_ids") or "[]")
    except json.JSONDecodeError:
        data["active_listing_ids"] = []
    data["focused_listing_id"] = data.get("focused_listing_id")
    return data


def set_pending_action(session_id: str, payload: dict[str, Any] | None) -> None:
    c = conn()
    c.execute(
        "UPDATE sessions SET pending_action=?, updated_at=? WHERE session_id=?",
        (json.dumps(payload or {}), now(), session_id),
    )
    c.commit()
    c.close()


def get_pending_action(session_id: str) -> dict[str, Any]:
    state = get_session_state(session_id)
    raw = state.get("pending_action") or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def add_message(user_id: str, session_id: str, role: str, content: str) -> None:
    c = conn()
    c.execute(
        "INSERT INTO messages(user_id,session_id,role,content,created_at) VALUES(?,?,?,?,?)",
        (user_id, session_id, role, content, now()),
    )
    c.commit()
    c.close()


def recent_messages(session_id: str, limit: int = 12) -> list[dict[str, str]]:
    c = conn()
    rows = c.execute(
        "SELECT role,content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    c.close()
    return [dict(r) for r in reversed(rows)]


def favorite(user_id: str, listing_id: int) -> None:
    c = conn()
    c.execute(
        "INSERT OR IGNORE INTO favorites(user_id,listing_id,created_at) VALUES(?,?,?)",
        (user_id, listing_id, now()),
    )
    c.commit()
    c.close()


def unfavorite(user_id: str, listing_id: int) -> None:
    c = conn()
    c.execute("DELETE FROM favorites WHERE user_id=? AND listing_id=?", (user_id, listing_id))
    c.commit()
    c.close()


def get_favorites(user_id: str) -> list[int]:
    c = conn()
    rows = c.execute(
        "SELECT listing_id FROM favorites WHERE user_id=? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    c.close()
    return [int(r["listing_id"]) for r in rows]


def create_booking(user_id: str, session_id: str, listing_id: int, appointment_at: str) -> tuple[bool, str]:
    ref = f"BK-{uuid.uuid4().hex[:8].upper()}"
    c = conn()
    try:
        with _lock:
            c.execute(
                "INSERT INTO bookings(booking_ref,user_id,session_id,listing_id,appointment_at,status,created_at) VALUES(?,?,?,?,?,?,?)",
                (ref, user_id, session_id, listing_id, appointment_at, "confirmed", now()),
            )
            c.commit()
        return True, ref
    except sqlite3.IntegrityError:
        return False, ""
    finally:
        c.close()


def save_lead(row: dict[str, Any]) -> str:
    path = Path(settings.leads_csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lead_id = row.get("lead_id") or f"LEAD-{uuid.uuid4().hex[:8].upper()}"
    row = {"lead_id": lead_id, "created_at": now(), **row}
    with _lock:
        exists = path.exists()
        with path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            if not exists:
                writer.writeheader()
            writer.writerow(row)
    return lead_id


def user_memory(user_id: str) -> dict[str, Any]:
    profile = get_profile(user_id)
    raw = profile.get("preferences") or ""
    recent_searches = [x.strip() for x in raw.split(" | ") if x.strip()]
    return {
        "name": profile.get("name") or user_id,
        "min_budget": profile.get("min_budget"),
        "max_budget": profile.get("max_budget"),
        "preferences": raw,
        "recent_searches": recent_searches,
        "favorite_listing_ids": get_favorites(user_id),
    }

"""SQLite layer for the matter file API.

Single-file database — Railway mounts a volume at /data so the SQLite file
survives redeploys. Falls back to ./matter.db locally.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import aiosqlite

# /data is the Railway volume mount; locally we keep the DB next to the code
DB_DIR = Path("/data") if Path("/data").is_dir() else Path(__file__).resolve().parent
DB_PATH = DB_DIR / "matter.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS matter_entries (
    id          TEXT PRIMARY KEY,
    card_data   TEXT NOT NULL,
    notes       TEXT NOT NULL DEFAULT '',
    added_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_added_at ON matter_entries(added_at DESC);
"""


async def init_db() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


def row_to_entry(row: aiosqlite.Row) -> dict:
    return {
        "id": row["id"],
        "card_data": json.loads(row["card_data"]),
        "notes": row["notes"] or "",
        "added_at": row["added_at"],
    }


async def list_entries(
    db: aiosqlite.Connection,
    *,
    category: str | None = None,
    search: str | None = None,
) -> list[dict]:
    query = "SELECT id, card_data, notes, added_at FROM matter_entries"
    where: list[str] = []
    params: list[object] = []
    if category:
        where.append("json_extract(card_data, '$.category') = ?")
        params.append(category)
    if search:
        # Scan the JSON blob plus notes — small dataset, simple is fine.
        where.append("(card_data LIKE ? OR notes LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like])
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY added_at DESC"
    async with db.execute(query, params) as cur:
        rows = await cur.fetchall()
    return [row_to_entry(r) for r in rows]


async def get_entry(db: aiosqlite.Connection, entry_id: str) -> dict | None:
    async with db.execute(
        "SELECT id, card_data, notes, added_at FROM matter_entries WHERE id = ?",
        (entry_id,),
    ) as cur:
        row = await cur.fetchone()
    return row_to_entry(row) if row else None


async def upsert_entry(db: aiosqlite.Connection, card_data: dict) -> dict:
    entry_id = card_data.get("id")
    if not entry_id:
        raise ValueError("card_data.id is required")
    payload = json.dumps(card_data, ensure_ascii=False)
    await db.execute(
        """
        INSERT INTO matter_entries (id, card_data) VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET card_data = excluded.card_data
        """,
        (entry_id, payload),
    )
    await db.commit()
    entry = await get_entry(db, entry_id)
    assert entry is not None
    return entry


async def delete_entry(db: aiosqlite.Connection, entry_id: str) -> bool:
    cur = await db.execute("DELETE FROM matter_entries WHERE id = ?", (entry_id,))
    await db.commit()
    return cur.rowcount > 0


async def update_notes(
    db: aiosqlite.Connection, entry_id: str, notes: str
) -> dict | None:
    cur = await db.execute(
        "UPDATE matter_entries SET notes = ? WHERE id = ?",
        (notes, entry_id),
    )
    await db.commit()
    if cur.rowcount == 0:
        return None
    return await get_entry(db, entry_id)


async def existing_ids(db: aiosqlite.Connection, ids: list[str]) -> set[str]:
    if not ids:
        return set()
    placeholders = ",".join("?" * len(ids))
    async with db.execute(
        f"SELECT id FROM matter_entries WHERE id IN ({placeholders})",
        ids,
    ) as cur:
        rows = await cur.fetchall()
    return {r["id"] for r in rows}

"""FastAPI matter file service.

Endpoints (mounted under /api):
    GET    /matter-file              list (?category=&search=)
    POST   /matter-file              add ({card_data: {...}})
    DELETE /matter-file/{id}         remove
    PATCH  /matter-file/{id}         update notes ({notes: "..."})
    GET    /matter-file/check        batch saved-id check (?ids=a,b,c)
    GET    /matter-file/export       download Markdown matter file
    GET    /health                   liveness probe

CORS is wide-open in v1 — the data here is non-sensitive debate prep and the
Railway URL is effectively a secret. Tighten in v2 if multi-user.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response

import database as db
import export as export_mod
from models import AddEntryRequest, CheckResponse, MatterEntry, NotesUpdate

log = logging.getLogger("matter-api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await db.init_db()
    log.info("matter file db ready at %s", db.DB_PATH)
    yield


app = FastAPI(title="Debate Digest Matter File API", version="1.0.0", lifespan=lifespan)

# Comma-separated list of allowed origins, or "*" for any. Default: any.
_origins = os.environ.get("CORS_ORIGINS", "*")
allow_origins = ["*"] if _origins.strip() == "*" else [o.strip() for o in _origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def db_dep():
    conn = await db.get_db()
    try:
        yield conn
    finally:
        await conn.close()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/matter-file", response_model=list[MatterEntry])
async def list_matter(
    category: str | None = None,
    search: str | None = None,
    conn=Depends(db_dep),
) -> list[dict]:
    return await db.list_entries(conn, category=category, search=search)


@app.post("/api/matter-file", response_model=MatterEntry)
async def add_matter(req: AddEntryRequest, conn=Depends(db_dep)) -> dict:
    card = req.card_data.model_dump()
    return await db.upsert_entry(conn, card)


@app.delete("/api/matter-file/{entry_id}")
async def delete_matter(entry_id: str, conn=Depends(db_dep)) -> dict:
    ok = await db.delete_entry(conn, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="not found")
    return {"deleted": entry_id}


@app.patch("/api/matter-file/{entry_id}", response_model=MatterEntry)
async def patch_notes(entry_id: str, body: NotesUpdate, conn=Depends(db_dep)) -> dict:
    entry = await db.update_notes(conn, entry_id, body.notes)
    if not entry:
        raise HTTPException(status_code=404, detail="not found")
    return entry


@app.get("/api/matter-file/check", response_model=CheckResponse)
async def check_matter(
    ids: str = Query("", description="Comma-separated card ids"),
    conn=Depends(db_dep),
) -> dict:
    id_list = [s for s in (ids.split(",") if ids else []) if s]
    saved = await db.existing_ids(conn, id_list)
    return {"saved": sorted(saved)}


@app.get("/api/matter-file/export")
async def export_matter(
    format: str = Query("md"),
    conn=Depends(db_dep),
):
    entries = await db.list_entries(conn)
    if format == "md":
        body = export_mod.render_matter_file(entries)
        return Response(
            content=body,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="matter-file.md"'},
        )
    raise HTTPException(status_code=400, detail=f"unsupported format: {format}")

"""Pydantic request/response shapes for the matter file API."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CardData(BaseModel):
    # Accept whatever the pipeline produces — keep this loose so we don't break
    # when the card schema evolves. Only `id` is strictly required for storage.
    id: str
    title: str | None = None
    source: str | None = None
    url: str | None = None
    published: str | None = None
    category: str | None = None
    region: str | None = None
    background: str | None = None
    prop_args: list[Any] = Field(default_factory=list)
    opp_args: list[Any] = Field(default_factory=list)
    weighing: str | None = None
    stock_connections: list[str] = Field(default_factory=list)
    motion_areas: list[str] = Field(default_factory=list)
    data_points: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class AddEntryRequest(BaseModel):
    card_data: CardData


class NotesUpdate(BaseModel):
    notes: str


class MatterEntry(BaseModel):
    id: str
    card_data: dict
    notes: str
    added_at: str


class CheckResponse(BaseModel):
    saved: list[str]

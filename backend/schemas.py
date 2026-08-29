
from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[str] = None


class CarFilter(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    min_price_aed: Optional[float] = None
    max_price_aed: Optional[float] = None
    min_mileage_km: Optional[float] = None
    max_mileage_km: Optional[float] = None
    keywords: list[str] = Field(default_factory=list)
    requires_gcc: bool = False
    requires_warranty: bool = False
    sort_by: Optional[str] = None
    limit: int = 8


class ParsedQuery(BaseModel):
    intent: str = "inventory_search"
    make: Optional[str] = None
    model: Optional[str] = None
    min_year: Optional[int] = None
    max_year: Optional[int] = None
    min_price_aed: Optional[float] = None
    max_price_aed: Optional[float] = None
    min_mileage_km: Optional[float] = None
    max_mileage_km: Optional[float] = None
    keywords: list[str] = Field(default_factory=list)
    requires_gcc: bool = False
    requires_warranty: bool = False
    sort_by: Optional[str] = None
    ordinal: Optional[int] = None
    listing_id: Optional[int] = None
    requires_clarification: bool = False
    show_all: bool = False
    limit: int = 8


class BookingDraft(BaseModel):
    listing_id: Optional[int] = None
    date: Optional[str] = None
    time: Optional[str] = None
    confirmed: bool = False


class LeadDraft(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    min_budget_aed: Optional[float] = None
    max_budget_aed: Optional[float] = None
    requirements: Optional[str] = None
    interested_listing_id: Optional[int] = None
    confirmed: bool = False


class ChatResponse(BaseModel):
    user_id: str
    session_id: str
    response: str
    intent: str
    matched_cars: list[dict[str, Any]] = Field(default_factory=list)
    total_matches: int = 0
    memory: dict[str, Any] = Field(default_factory=dict)
    booking: Optional[dict[str, Any]] = None
    lead: Optional[dict[str, Any]] = None
    meta: dict[str, Any] = Field(default_factory=dict)

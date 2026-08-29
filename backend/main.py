from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .agent import agent
from .inventory import inventory
from .llm import gemini
from .schemas import CarFilter, ChatRequest, ChatResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="dubizzle Cars — Grounded Inventory API",
    version="2.0.0",
    description="FastAPI backend for a grounded conversational dubizzle Cars assistant.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "project": "dubizzle Cars",
        "inventory_rows": len(inventory.df),
        "llm_enabled": gemini.available,
        "source": "provided Excel only",
    }


@app.get("/inventory/summary")
def inventory_summary():
    return inventory.summary()


@app.post("/inventory/search")
def inventory_search(filters: CarFilter):
    cars = inventory.search(filters)
    return {"filters": filters.model_dump(), "total_matches": inventory.search_count(filters), "cars": cars}


@app.get("/inventory/{listing_id}")
def inventory_item(listing_id: int):
    car = inventory.get(listing_id)
    if not car:
        raise HTTPException(status_code=404, detail="Listing not found")
    return car


@app.get("/users/{user_id}/memory")
def user_memory(user_id: str):
    return db.user_memory(user_id)


@app.get("/users/{user_id}/favorites")
def favorites(user_id: str):
    return {"cars": [inventory.get(i) for i in db.get_favorites(user_id) if inventory.get(i)]}


@app.post("/users/{user_id}/favorites/{listing_id}")
def add_favorite(user_id: str, listing_id: int):
    if not inventory.get(listing_id):
        raise HTTPException(status_code=404, detail="Listing not found")
    db.favorite(user_id, listing_id)
    return {"status": "saved", "listing_id": listing_id}


@app.delete("/users/{user_id}/favorites/{listing_id}")
def remove_favorite(user_id: str, listing_id: int):
    db.unfavorite(user_id, listing_id)
    return {"status": "removed", "listing_id": listing_id}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    try:
        return agent.chat(request.user_id.strip(), request.session_id, request.message.strip())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {exc}") from exc


from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from .config import settings


class LLMQuery(BaseModel):
    intent: str = "inventory_search"
    make: str | None = None
    model: str | None = None
    min_year: int | None = None
    max_year: int | None = None
    min_price_aed: float | None = None
    max_price_aed: float | None = None
    min_mileage_km: float | None = None
    max_mileage_km: float | None = None
    keywords: list[str] = Field(default_factory=list)
    requires_gcc: bool = False
    requires_warranty: bool = False
    sort_by: str | None = None
    requires_clarification: bool = False


class GeminiClient:
    def __init__(self):
        self.client = None
        if settings.gemini_api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=settings.gemini_api_key)
            except Exception:
                self.client = None

    @property
    def available(self) -> bool:
        return self.client is not None

    def parse_query(self, message: str, known_makes: list[str], known_models: list[str]) -> dict[str, Any] | None:
        if not self.client:
            return None

        schema = LLMQuery.model_json_schema()
        system = f"""
You are the natural-language query interpreter for a used-car assistant.
You MUST only extract constraints explicitly stated or strongly implied by the user's
automotive request. Never invent a price, mileage, body type, feature, make or model.

Known makes from the provided inventory: {known_makes}
Known models from the provided inventory: {known_models}

Intent must be one of: inventory_search, booking, lead, favorite, general_chat, unknown.
Use inventory_search for recommendations, filtering, car details, features, comparisons.
Use booking for viewing/test-drive requests.
Use lead for contact/sales enquiry.
Use favorite when the user says they like/save/favourite a car.
Use general_chat for greetings or simple automotive small talk.
Use unknown for non-automotive requests.

Price means CASH PRICE in AED only. If the user mentions monthly payments,
do not put that number in min_price_aed/max_price_aed.
For phrases like "under 100k", convert 100k to 100000.
For "newest", set sort_by=newest. For "cheapest", set sort_by=lowest_price.
For "GCC" requirements set requires_gcc=true. For "with warranty" set requires_warranty=true.
For "lowest mileage", set sort_by=lowest_mileage.

Return JSON matching this schema exactly:
{json.dumps(schema)}
"""
        try:
            response = self.client.models.generate_content(
                model=settings.gemini_model,
                contents=f"{system}\n\nUSER MESSAGE:\n{message}",
                config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                    "temperature": settings.model_temperature,
                },
            )
            return json.loads(response.text)
        except Exception:
            return None

    def polish(self, user_message: str, grounded_payload: dict[str, Any]) -> str | None:
        if not self.client:
            return None
        system = """
You are the voice layer of a used-car marketplace assistant.
The payload below is the ONLY source of vehicle facts. Do not add facts, prices,
mileage, warranty, location, features, availability, or specifications that are
not in the payload. Be concise, helpful, and natural. If a field is null, say it
is not stated in the listing. Never mention competitors. Never answer coding,
history, politics, or unrelated requests.
"""
        try:
            response = self.client.models.generate_content(
                model=settings.gemini_model,
                contents=f"{system}\nUSER:\n{user_message}\nGROUNDED PAYLOAD:\n{json.dumps(grounded_payload, ensure_ascii=False)}",
                config={"temperature": 0.2, "max_output_tokens": 350},
            )
            return response.text.strip()
        except Exception:
            return None


gemini = GeminiClient()

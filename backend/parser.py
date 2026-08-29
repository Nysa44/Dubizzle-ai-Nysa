
from __future__ import annotations

import re
from typing import Any

from .inventory import Inventory
from .schemas import ParsedQuery


def _money(value: str) -> float:
    value = value.lower().replace(",", "").strip()
    if value.endswith("k"):
        return float(value[:-1]) * 1000
    if value.endswith("m"):
        return float(value[:-1]) * 1_000_000
    return float(value)


def deterministic_parse(message: str, inventory: Inventory) -> ParsedQuery:
    m = message.lower().strip()

    guardrail_terms = [
        "write code", "python code", "javascript", "write a program",
        "history question", "who was napoleon", "world war 2", "politics",
        "solve this math", "solve a math", "math problem", "mathematics",
        "competitor", "competitors", "other used car platform",
        "cars24", "cars 24", "carswitch", "car switch", "yallamotor",
        "yalla motor", "dubicars", "dubai cars platform",
    ]
    if any(x in m for x in guardrail_terms) or re.fullmatch(
        r"(?:what is|what's|calculate|compute|solve)\s+[-+*/%()\d\s]+\??", m
    ):
        return ParsedQuery(intent="unknown")

    # Keep short conversational messages out of inventory retrieval. Exact
    # greetings such as "hi" must not fall through to a 100-listing search.
    chat_phrases = {
        "hi", "hello", "hey", "hiya", "yo", "thanks", "thank you",
        "thx", "thank u", "thanks a lot", "thank you so much", "ok", "okay",
        "cool", "great", "nice", "yes", "yeah", "yep", "sure", "continue",
        "no", "nope", "nah",
    }
    if m in chat_phrases:
        intent = "general_chat"
    elif re.fullmatch(r"(?:my name is|call me)\s+[a-z][a-z .'-]{1,39}", m, re.I):
        intent = "general_chat"
    elif any(x in m for x in ["book", "test drive", "test-drive", "viewing", "appointment"]):
        intent = "booking"
    elif any(x in m for x in ["contact me", "call me", "sales", "buying enquiry", "buying inquiry", "lead"]) or re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", m) or re.search(r"(?:\+971|0)?[\s-]?(?:\d[\s-]?){8,12}\b", m):
        intent = "lead"
    elif any(x in m for x in ["i like", "i love", "save this", "save it", "favourite", "favorite", "favourites", "favorites", "what have i saved", "what did i save", "what cars have i saved", "what are my saved cars", "show my saved cars"]):
        intent = "favorite"
    elif any(x in m for x in ["hello", "hi ", "hey", "good morning", "good afternoon", "good evening", "thanks", "thank you", "thx"]):
        intent = "general_chat"
    else:
        # Fail closed: only positively recognised automotive/inventory
        # language may reach retrieval. Unknown or irrelevant text must never
        # fall through to the generic 100-listing inventory search.
        automotive_signals = [
            "car", "cars", "vehicle", "vehicles", "listing", "listings",
            "inventory", "sedan", "suv", "coupe", "convertible", "hatchback",
            "wagon", "pickup", "truck", "awd", "4wd", "gcc", "warranty",
            "mileage", "odometer", "engine", "horsepower", "bhp", "transmission",
            "drivetrain", "price", "cash price", "monthly", "payment", "trim",
            "spec", "sunroof", "panoramic", "turbo", "accident", "paint",
            "colour", "color", "leather", "carplay", "android auto",
            "seven seats", "7 seats", "7 seat", "test drive", "showroom",
            "managed car", "shortlist", "cheapest", "most expensive",
            "newest", "oldest", "under aed", "under ", "below aed",
            "between aed",
        ]
        make_alias_words = [
            "mercedes", "mercedes benz", "benz", "bmw", "bmws",
            "rolls royce", "land rover", "range rover",
        ]
        has_make = (
            any(re.search(rf"\b{re.escape(make)}s?\b", m) for make in inventory.makes)
            or any(re.search(rf"\b{re.escape(alias)}s?\b", m) for alias in make_alias_words)
        )
        has_model = any(re.search(rf"\b{re.escape(model)}\b", m) for model in inventory.models)
        # Common marketplace shorthand such as "GLS" is resolved to the
        # canonical model below, but must also count as automotive language.
        has_model = has_model or bool(re.search(
            r"\b(?:gls|x1|x6|q7|c200|c300|c43|e350|gt)\b", m
        ))
        has_signal = any(x in m for x in automotive_signals)
        has_ordinal = bool(re.search(
            r"\b(?:first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\b", m
        ))
        has_followup = bool(re.search(
            r"\b(?:it|that one|this one|that car|this car|same car)\b", m
        ))
        intent = "inventory_search" if (has_signal or has_make or has_model or has_ordinal or has_followup) else "unknown"

    result = ParsedQuery(intent=intent)

    # Exact inventory vocabulary matching, plus common marketplace aliases.
    # Keep the canonical value from the Excel inventory.
    make_aliases = {
        "mercedes": "mercedes-benz",
        "mercedes benz": "mercedes-benz",
        "benz": "mercedes-benz",
        "bmw": "bmw",
        "rolls royce": "rolls-royce",
        "land rover": "land-rover",
        "range rover": "land-rover",
    }
    for alias, canonical in make_aliases.items():
        if canonical in inventory.makes and re.search(rf"\b{re.escape(alias)}\b", m):
            result.make = canonical
            break
    if result.make is None:
        for make in inventory.makes:
            if re.search(rf"\b{re.escape(make)}s?\b", m):
                result.make = make
                break
    for model in inventory.models:
        if re.search(rf"\b{re.escape(model)}\b", m):
            result.model = model
            break
    # Natural marketplace shorthand: "GLS" -> the inventory's canonical "gls-class".
    if result.model is None:
        normalized_models = []
        for model in inventory.models:
            base = re.sub(r"[- ]?class$", "", model).replace("-", " ").strip()
            normalized_models.append((base, model))
        hits = [(base, model) for base, model in normalized_models if base and re.search(rf"\b{re.escape(base)}\b", m)]
        if len(hits) == 1:
            result.model = hits[0][1]

    years = [int(x) for x in re.findall(r"\b(19\d{2}|20\d{2})\b", m)]
    if years:
        if "between" in m and len(years) >= 2:
            result.min_year, result.max_year = min(years), max(years)
        elif any(token in m for token in ["after", "from", "since"]):
            result.min_year = max(years)
        elif any(token in m for token in ["before", "until", "upto", "up to"]):
            result.max_year = min(years)
        else:
            result.min_year = result.max_year = years[0]

    price_match = re.search(r"(?:under|below|less than|up to|max(?:imum)?|budget(?: of)?|within)\s*(?:aed\s*)?([\d,.]+[km]?)", m)
    if price_match:
        result.max_price_aed = _money(price_match.group(1))
    else:
        aed_matches = re.findall(r"(?:aed\s*)?([\d,.]+[km]?)\s*(?:aed|dh|dhs)", m)
        if aed_matches and ("monthly" not in m and "/mo" not in m and "per month" not in m):
            vals = [_money(v) for v in aed_matches if _money(v) >= 3000]
            if vals:
                result.max_price_aed = max(vals)

    between = re.search(
        r"(?:between|from)\s*(?:aed\s*)?([\d,.]+[km]?)\s*(?:and|to|-)\s*(?:aed\s*)?([\d,.]+[km]?)",
        m,
    )
    if between:
        result.min_price_aed = _money(between.group(1))
        result.max_price_aed = _money(between.group(2))

    mileage = re.search(r"(?:under|below|less than)\s*([\d,.]+)\s*(?:k\s*)?(?:km|kms)", m)
    if mileage:
        value = float(mileage.group(1).replace(",", ""))
        if "k" in mileage.group(0).lower():
            value *= 1000
        result.max_mileage_km = value

    if "newest" in m or "latest model" in m:
        result.sort_by = "newest"
    elif "oldest" in m:
        result.sort_by = "oldest"
    elif "cheapest" in m or "lowest price" in m:
        result.sort_by = "lowest_price"
    elif any(x in m for x in ["most expensive", "highest price", "priciest", "highest priced", "costliest"]):
        result.sort_by = "highest_price"
    elif "lowest mileage" in m or "least mileage" in m:
        result.sort_by = "lowest_mileage"

    keyword_map = {
        "gcc": "gcc",
        "warranty": "warranty",
        "sunroof": "sunroof",
        "apple carplay": "apple carplay",
        "android auto": "android auto",
        "awd": "awd",
        "4wd": "4wd",
        "leather": "leather",
        "convertible": "convertible",
        "coupe": "coupe",
        "suv": "suv",
        "sedan": "sedan",
        "0km": "0km",
        "brand new": "brand new",
        "single hand": "single hand",
        "white": "white",
        "black": "black",
        "red": "red",
        "blue": "blue",
        "silver": "silver",
        "grey": "grey",
        "gray": "gray",
        "beige": "beige",
        "brown": "brown",
        "petrol": "petrol",
        "diesel": "diesel",
        "hybrid": "hybrid",
        "electric": "electric",
        "automatic": "automatic",
        "manual": "manual",
        "leather": "leather",
        "parking camera": "parking camera",
        "sunroof": "sunroof",
        "service history": "service history",
        "single owner": "single owner",
        "7 seats": "seven_seat",
        "7 seat": "seven_seat",
        "7-seater": "seven_seat",
        "seven seats": "seven_seat",
        "panoramic roof": "panoramic",
        "panoramic sunroof": "panoramic",
        "panorama roof": "panoramic",
        "accident free": "accident_free",
        "accident-free": "accident_free",
        "no accidents": "accident_free",
        "turbo engine": "turbo",
        "turbo engines": "turbo",
        "turbocharged": "turbo",
    }
    for phrase, key in keyword_map.items():
        if phrase in m:
            result.keywords.append(key)

    # Structured marketplace requirements. These are filters, not loose text
    # keywords, so "GCC car with warranty" means BOTH conditions must hold.
    result.requires_gcc = bool(re.search(r"\bgcc\b", m))
    result.requires_warranty = bool(re.search(r"\bwith\s+(?:an?\s+)?warranty\b|\bwarranty\s+(?:included|provided|stated|available)\b", m))

    result.show_all = bool(
        re.search(r"\bshow(?: me)?\s+all\s+(?:matching\s+)?(?:cars|listings|matches|results)\b", m)
        or (re.search(r"\bshow(?: me)?\s+all\b", m) and (result.make or result.model) and "details" not in m and "everything" not in m)
    )

    # Ordinal references are handled before search.
    ordinal_map = {
        "first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3,
        "fourth": 4, "4th": 4, "fifth": 5, "5th": 5,
    }
    for token, value in ordinal_map.items():
        if re.search(rf"\b{re.escape(token)}\b", m):
            result.ordinal = value
            break

    id_match = re.search(r"(?:listing|car|#)\s*(?:id\s*)?(\d{1,3})\b", m)
    if id_match:
        result.listing_id = int(id_match.group(1))

    # Never pass ranking words through as literal inventory keywords.
    ranking_words = {"newest", "latest", "oldest", "cheapest", "lowest", "price", "mileage"}
    result.keywords = [k for k in result.keywords if k not in ranking_words]
    return result

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from . import db
from .inventory import inventory
from .llm import gemini
from .parser import deterministic_parse
from .schemas import ParsedQuery

DUBAI = ZoneInfo("Asia/Dubai")
DETAIL_WORDS = [
    "mileage", "odometer", "warranty", "price", "cash price", "trim", "spec", "description", "details",
    "speed", "horsepower", "bhp", " hp", "engine", "acceleration", "0-100", "monthly", "payment",
    "color", "colour", "interior", "exterior", "transmission", "gear", "torque", "fuel", "owner", "service", "keys", "agency",
    "registration", "insurance", "condition", "accident", "drivetrain", "drive type", "drive", "accidents", "paint", "repaint", "history", "features", "equipment", "sunroof", "camera", "carplay", "android", "agency", "agencies", "keys", "dealer", "showroom", "where", "from", "origin", "country", "everything", "verify", "verified",
]


def money(v: float | None) -> str:
    return "Price not stated" if v is None else f"AED {v:,.0f}"


def car_label(car: dict[str, Any]) -> str:
    return f"{car['year']} {car['make'].title()} {car['model'].title()}"


def is_inventory_wide_attribute_query(message: str) -> bool:
    """True for plural attribute/feature requests that must scan the inventory."""
    m = re.sub(r"\s+", " ", message.lower().strip())
    return bool(re.search(
        r"(?:^|\b)(?:which|what)\s+(?:cars|vehicles|listings)\b|"
        r"(?:^|\b)show(?: me)?\s+(?:cars|vehicles|listings)\b|"
        r"(?:^|\b)(?:cars|vehicles|listings)\s+(?:with|that have|mention|featuring)\b",
        m,
    ))


def context_listing(user_id: str, session_id: str, parsed: ParsedQuery, message: str) -> int | None:
    if is_inventory_wide_attribute_query(message):
        return None
    if parsed.listing_id:
        return parsed.listing_id
    state = db.get_session_state(session_id)

    # Booking is deliberately stricter than ordinary detail follow-ups.
    # A bare "I want to book" must NEVER inherit the focused/first result,
    # because that can silently book an unrelated car. Only an explicit
    # ordinal or an explicit reference such as "that one" may select it.
    if parsed.intent == "booking":
        ids = state.get("active_listing_ids", [])
        if parsed.ordinal and 1 <= parsed.ordinal <= len(ids):
            return int(ids[parsed.ordinal - 1])
        if re.search(r"\b(it|that car|this car|that one|this one|the same car|same car)\b", message.lower()) and ids:
            return int(ids[0])
        # If the latest search resolved to exactly one car, a bare booking
        # request can safely continue with that single focused result. This
        # avoids forcing the user to repeat "this one" after an exact listing
        # lookup, while still refusing to guess when the result set has
        # multiple cars.
        if len(ids) == 1:
            return int(ids[0])
        return None
    ids = state.get("active_listing_ids", [])
    if parsed.ordinal and 1 <= parsed.ordinal <= len(ids):
        return int(ids[parsed.ordinal - 1])
    if re.search(r"\b(it|that car|this car|the car|that one|this one|the same car|same car)\b", message.lower()) and ids:
        return int(ids[0])
    # Detail-only follow-ups such as "what's the engine?" or "what's the price?"
    # refer to the current primary result instead of launching a new inventory search.
    focused = state.get("focused_listing_id")
    if focused and int(focused) in [int(x) for x in ids]:
        return int(focused)
    if ids and any(word in message.lower() for word in DETAIL_WORDS):
        return int(ids[0])
    return None


def parse_booking_date_time(message: str) -> tuple[str | None, str | None]:
    m = message.lower(); now = datetime.now(DUBAI)
    tm = re.search(r"(?:at|@|around)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", m) or re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", m)
    time_str = None
    if tm:
        hour = int(tm.group(1)); minute = int(tm.group(2) or 0); suffix = tm.group(3)
        if suffix == "pm" and hour < 12: hour += 12
        if suffix == "am" and hour == 12: hour = 0
        if suffix is None and hour < 8: hour += 12
        if 0 <= hour <= 23 and minute < 60: time_str = f"{hour:02d}:{minute:02d}"
    dm = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", m)
    if dm: return f"{int(dm.group(1)):04d}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}", time_str
    if "today" in m: return now.date().isoformat(), time_str
    if "tomorrow" in m: return (now + timedelta(days=1)).date().isoformat(), time_str
    weekdays = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6}
    for day, target in weekdays.items():
        if day in m:
            delta = (target - now.weekday()) % 7
            if delta == 0: delta = 7
            return (now + timedelta(days=delta)).date().isoformat(), time_str
    return None, time_str


def booking_response(user_id: str, session_id: str, message: str, listing_id: int | None):
    pending = db.get_pending_action(session_id)
    if not listing_id and pending.get("type") == "booking": listing_id = pending.get("listing_id")
    car = inventory.get(listing_id) if listing_id else None
    if not car:
        # Keep the booking flow alive while asking the user to choose a car.
        # The next turn may be an ordinal ("the third one") and must resolve
        # against the current result set rather than becoming a new search.
        db.set_pending_action(session_id, {"type":"booking", "listing_id": None})
        return "Absolutely — I can arrange a viewing. Which car would you like to see? You can say “the second one” after a search.", {"status":"needs_car"}, []
    date_str, time_str = parse_booking_date_time(message)
    if pending.get("type") == "booking" and re.search(r"\b(confirm|yes|book it|go ahead)\b", message.lower()) and pending.get("appointment_at"):
        pdt = datetime.fromisoformat(pending["appointment_at"]); date_str, time_str = pdt.date().isoformat(), pdt.strftime("%H:%M")
    if not date_str or not time_str:
        db.set_pending_action(session_id, {"type":"booking","listing_id":car["listing_id"]})
        return f"Great choice — {car_label(car)} is selected. Viewings are available Monday to Saturday, 8:00 AM–8:00 PM. Tell me a day and time, for example “Saturday at 3 PM”.", {"status":"needs_datetime","listing_id":car["listing_id"]}, [car]
    dt = datetime.fromisoformat(f"{date_str}T{time_str}:00").replace(tzinfo=DUBAI)
    if dt.weekday() == 6:
        return "Sunday isn't available for managed-car viewings. Please choose Monday to Saturday, between 8:00 AM and 8:00 PM.", {"status":"invalid_day","listing_id":car["listing_id"]}, [car]
    if dt.hour < 8 or dt.hour > 20 or (dt.hour == 20 and dt.minute > 0):
        return "That time is outside the viewing window. Please choose a time from 8:00 AM to 8:00 PM, Monday to Saturday.", {"status":"invalid_time","listing_id":car["listing_id"]}, [car]
    if dt <= datetime.now(DUBAI):
        return "I can only book a future viewing. Please choose a future date and time.", {"status":"past_time","listing_id":car["listing_id"]}, [car]
    # A valid date/time completes the simulated pre-booking.
    ok, ref = db.create_booking(user_id, session_id, car["listing_id"], dt.isoformat())
    if not ok:
        return "That exact slot is already booked for this listing. Please choose another time.", {"status":"slot_taken","listing_id":car["listing_id"]}, [car]
    db.set_pending_action(session_id, None)
    return f"You're booked. **{car_label(car)}** is confirmed for **{dt.strftime('%A, %d %b %Y at %I:%M %p')}**. Your reference is **#{ref}**.", {"status":"confirmed","reference":ref,"listing_id":car["listing_id"],"appointment_at":dt.isoformat()}, [car]


def lead_response(user_id: str, session_id: str, message: str, active_listing_id: int | None):
    m = message.lower(); profile = db.get_profile(user_id); bmin, bmax = profile.get("min_budget"), profile.get("max_budget")
    def parse_money(s):
        s=s.lower().replace(",",""); return float(s[:-1])*1000 if s.endswith("k") else float(s[:-1])*1000000 if s.endswith("m") else float(s)
    rng = re.search(r"(?:between|from)\s*(?:aed\s*)?([\d,.]+[km]?)\s*(?:and|to|-)\s*(?:aed\s*)?([\d,.]+[km]?)", m)
    if not rng:
        rng = re.fullmatch(r"(?:aed\s*)?([\d,.]+[km]?)\s*(?:-|to|and)\s*(?:aed\s*)?([\d,.]+[km]?)", m.strip())
    # Accept natural lead wording such as "my budget is AED 300,000" and
    # "50-300k". These are conversational lead values, not inventory-only
    # filters.
    natural_budget = re.search(r"(?:my\s+)?budget\s*(?:is|of|:)?\s*(?:aed\s*)?([\d,.]+[km]?)", m)
    under = re.search(r"(?:under|below|up to|max(?:imum)?|budget(?:\s+(?:is|of))?)\s*(?:aed\s*)?([\d,.]+[km]?)", m)
    if rng: bmin,bmax=parse_money(rng.group(1)),parse_money(rng.group(2))
    elif natural_budget: bmax=parse_money(natural_budget.group(1))
    elif under: bmax=parse_money(under.group(1))
    phone = None; pm = re.search(r"(?:\+971|0)?[\s-]?(?:\d[\s-]?){8,12}\b", message)
    if pm: phone=re.sub(r"[^\d+]", "", pm.group(0))
    email=None; em=re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", message)
    if em: email=em.group(0)
    for prior in reversed(db.recent_messages(session_id, limit=12)):
        if prior["role"] != "user": continue
        if not phone:
            pm=re.search(r"(?:\+971|0)?[\s-]?(?:\d[\s-]?){8,12}\b", prior["content"])
            if pm: phone=re.sub(r"[^\d+]", "", pm.group(0))
        if not email:
            em=re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", prior["content"])
            if em: email=em.group(0)
    nm=re.search(r"(?:my name is|i am|i'm)\s+([A-Za-z][A-Za-z .'-]{1,40}?)(?=\s+and\s+my\s+(?:phone|email)\b|\s+and\s+|$)",message,re.I); name=nm.group(1).strip() if nm else None
    if bmin is not None or bmax is not None: db.update_profile(user_id,min_budget=bmin,max_budget=bmax)
    if name: db.update_profile(user_id,name=name)
    requirements = message.strip() if len(message.strip())>5 else None
    if email or phone:
        for previous in reversed([x["content"] for x in db.recent_messages(session_id,12) if x["role"]=="user" and x["content"]!=message]):
            if len(previous) <= 8:
                continue
            if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", previous) or re.search(r"(?:\+971|0)?[\s-]?(?:\d[\s-]?){8,12}\b", previous):
                continue
            if re.fullmatch(r"(?:my name is|call me|i am|i'm)\s+[A-Za-z][A-Za-z .'-]{1,40}", previous.strip(), re.I):
                continue
            need_match = re.search(r"(?:i need|need|looking for|want)\s+(.+)$", previous, re.I)
            requirements = need_match.group(1).strip().rstrip(".") if need_match else previous.strip()
            if requirements:
                break
    draft={"status":"collecting","min_budget_aed":bmin,"max_budget_aed":bmax,"phone":phone,"email":email,"requirements":requirements,"interested_listing_id":active_listing_id}
    if bmin is None and bmax is None:
        db.set_pending_action(session_id,{"type":"lead"})
        return "Happy to help. What price range are you shopping within?",draft,[]
    if not requirements:
        db.set_pending_action(session_id,{"type":"lead"})
        return "Got it. What matters most to you — make, model, features, GCC spec, warranty, body type, or another requirement?",draft,[]
    if not (phone or email):
        db.set_pending_action(session_id,{"type":"lead"})
        return "Perfect. To qualify the enquiry, please share a phone number or email address.",draft,[]
    confirm=bool(re.search(r"\b(confirm|yes|submit|save lead|go ahead)\b",m))
    if not confirm:
        db.set_pending_action(session_id,{"type":"lead"}); budget=f"up to {money(bmax)}" if bmax is not None and bmin is None else f"{money(bmin)}–{money(bmax)}"
        return f"Here’s the enquiry I can save: budget {budget}, need: “{requirements}”. Reply **confirm** and I’ll record it.",draft|{"status":"awaiting_confirmation"},[]
    lead_id=db.save_lead({"user_id":user_id,"session_id":session_id,"name":profile.get("name") or name or user_id,"phone":phone or "","email":email or "","min_budget_aed":bmin or "","max_budget_aed":bmax or "","requirements":requirements or "","interested_listing_id":active_listing_id or ""})
    db.set_pending_action(session_id,None)
    return f"Done — your enquiry is saved as **#{lead_id}**. I’ve kept your budget and requirements with your profile for future conversations.",draft|{"status":"saved","lead_id":lead_id},[]


def _source_snippets(car: dict[str, Any], query: str, limit: int = 5) -> list[str]:
    """Return concise, query-relevant snippets from the selected listing only."""
    text = car.get("description", "")
    if not text:
        return []
    q = query.lower()

    # High-confidence marketplace phrases. These are intentionally source-only.
    targeted_patterns = []
    if "agency" in q and ("key" in q or "keys" in q):
        targeted_patterns += [r"two\s+agency\s+keys?", r"agency\s+keys?"]
    if any(x in q for x in ["accident", "paint", "repaint", "scratch"]):
        targeted_patterns += [
            r"completely\s+free\s+of\s+paint,\s*accidents(?:\s+and)?\s+scratches",
            r"no\s+accidents?\s*,?\s*no\s+repaints?",
            r"free\s+accident",
            r"original\s+paint",
        ]
    if any(x in q for x in ["dealer", "showroom"]):
        targeted_patterns += [r"(?:showroom|dealer)[^.]{0,140}", r"[A-Za-z0-9 .&-]+MOTORS"]
    if any(x in q for x in ["service", "serviced", "maintenance"]):
        targeted_patterns += [r"fully\s+serviced[^.]{0,120}", r"major\s+service[^.]{0,140}", r"new\s+shocks[^.]{0,100}"]
    if any(x in q for x in ["carplay", "android"]):
        targeted_patterns += [r"carplay[^.]{0,100}", r"android\s+auto[^.]{0,100}"]
    if any(x in q for x in ["sunroof", "panoramic"]):
        targeted_patterns += [r"panoramic[^.]{0,100}", r"sunroof[^.]{0,100}"]

    found=[]
    for pattern in targeted_patterns:
        for m in re.finditer(pattern, text, re.I):
            snippet=re.sub(r"\s+", " ", m.group(0)).strip(" -:;|•")
            if snippet and snippet.lower() not in {x.lower() for x in found}:
                found.append(snippet)
            if len(found)>=limit:
                return found
    if found:
        return found

    vehicle_words = set(re.findall(r"[a-z0-9]+", f"{car.get('make','')} {car.get('model','')} {car.get('trim','')}".lower()))
    terms = [
        t for t in re.findall(r"[a-z0-9]+", q)
        if len(t) >= 3 and t not in {
            "what", "whats", "what's", "the", "this", "that", "car", "one",
            "listing", "tell", "about", "does", "have", "has", "is", "are",
            "its", "it", "first", "second", "third", "fourth", "fifth",
            "please", "can", "you", "from", "where", "everything", "all", "verify", "verified",
        } and t not in vehicle_words
    ]
    aliases = {
        "accident": ["accident", "accidents", "paint", "repaint"],
        "paint": ["paint", "repaint", "accident"],
        "agency": ["agency", "keys"],
        "key": ["keys", "key"],
        "dealer": ["dealer", "showroom"],
        "showroom": ["showroom", "dealer"],
    }
    expanded=[]
    for t in terms: expanded.extend(aliases.get(t,[t]))
    terms=list(dict.fromkeys(expanded))
    chunks=[re.sub(r"\s+", " ", x).strip(" -:;|•") for x in re.split(r"\s*[•|]\s*|(?<=[.!?])\s+", text)]
    chunks=[x for x in chunks if len(x)>=4]
    hits=[]
    for chunk in chunks:
        score=sum(1 for t in terms if re.search(rf"\b{re.escape(t)}\b", chunk.lower()))
        if score: hits.append((score,chunk))
    if hits:
        hits.sort(key=lambda x:(-x[0],len(x[1])))
        return [x[1] for x in hits[:limit]]
    return []

def _extract_warranty_evidence(description: str) -> str | None:
    """Return the shortest explicit included-warranty phrase from the listing."""
    text = re.sub(r"\s+", " ", description or "").strip()
    patterns = [
        r"\b\d+\s+Years?\s+[A-Za-z][A-Za-z®& -]*?\s+Warranty\b",
        r"\b[A-Za-z][A-Za-z®& -]{0,60}\s+Warranty\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            value = m.group(0).strip(" .,-")
            if "can be arranged" not in value.lower():
                return value
    return None

def _detail_answer(message: str, car: dict[str, Any]) -> str:
    """Answer only from the selected listing's structured facts and raw description."""
    q = message.lower()
    lines: list[str] = []

    def add(label: str, value: Any, evidence: str | None = None):
        if value is None:
            value = "Not stated in the listing"
        text = f"**{label}:** {value}"
        if evidence:
            text += f"\n_Source: {evidence}_"
        lines.append(text)

    # Direct structured fields.
    if "price" in q or "cost" in q or "expensive" in q:
        add("Cash price", money(car.get("price_aed")), car.get("price_evidence"))
        if car.get("monthly_aed") is not None:
            add("Monthly payment", f"AED {car['monthly_aed']:,.0f}", car.get("monthly_evidence"))
    if "mileage" in q or "odometer" in q:
        add("Mileage", f"{car['mileage_km']:,.0f} km" if car.get("mileage_km") is not None else None, car.get("mileage_evidence"))
    if "top speed" in q or ("speed" in q and "horsepower" not in q):
        if car.get("top_speed_mph") is not None:
            add("Top speed", f"{car['top_speed_mph']:,.0f} mph (~{car['top_speed_kmh']:,.0f} km/h)", car.get("speed_mph_evidence") or car.get("speed_kmh_evidence"))
        elif car.get("top_speed_kmh") is not None:
            add("Top speed", f"{car['top_speed_kmh']:,.0f} km/h", car.get("speed_kmh_evidence"))
        else: add("Top speed", None)
    if any(x in q for x in ["horsepower", "bhp", " hp"]):
        add("Horsepower", f"{car['horsepower']:,.0f} hp" if car.get("horsepower") is not None else None, car.get("horsepower_evidence"))
    if "engine" in q:
        engine_value = f"{car['engine_l']:g} L" if car.get("engine_l") is not None else None
        if car.get("engine_evidence") and any(k in car["engine_evidence"].lower() for k in ["turbo", "supercharged"]):
            engine_value = car["engine_evidence"]
        add("Engine", engine_value, car.get("engine_evidence"))
    if "warranty" in q:
        warranty_value = None
        warranty_evidence = None
        if car.get("warranty") is True:
            warranty_evidence = _extract_warranty_evidence(car.get("description", ""))
            warranty_value = warranty_evidence or "Warranty stated"
        elif car.get("warranty") is False:
            warranty_value = "No warranty"
        add("Warranty", warranty_value, warranty_evidence)
    if "acceleration" in q or "0-100" in q or "0–100" in q:
        add("0–100 km/h", f"{car['acceleration_0_100_s']:g} s" if car.get("acceleration_0_100_s") is not None else None, car.get("acceleration_evidence"))
    if "monthly" in q or "installment" in q or "per month" in q:
        add("Monthly payment", f"AED {car['monthly_aed']:,.0f}" if car.get("monthly_aed") is not None else None, car.get("monthly_evidence"))
    if "spec" in q or "gcc" in q or "american" in q or "european" in q or "korean" in q or "where" in q or "origin" in q or "country" in q or "from" in q:
        add("Regional specification", car.get("regional_spec"))
    if "exterior colour" in q or "exterior color" in q or re.search(r"\bcolour\b", q) or re.search(r"\bcolor\b", q):
        add("Exterior colour", car.get("exterior_colour"), car.get("exterior_colour_evidence"))

    if "condition" in q or "accident" in q or "paint" in q or "repaint" in q or "history" in q:
        add("Condition / accident history", car.get("condition"), car.get("condition_evidence"))

    # Broad detail requests: expose the structured facts that are actually known,
    # then add source snippets for facts that don't fit predefined fields.
    broad = any(x in q for x in ["everything", "all details", "all the details", "everything you can verify", "full details"])
    if broad:
        known = [
            ("Cash price", money(car.get("price_aed")) if car.get("price_aed") is not None else None, car.get("price_evidence")),
            ("Monthly payment", f"AED {car['monthly_aed']:,.0f}" if car.get("monthly_aed") is not None else None, car.get("monthly_evidence")),
            ("Mileage", f"{car['mileage_km']:,.0f} km" if car.get("mileage_km") is not None else None, car.get("mileage_evidence")),
            ("Engine", f"{car['engine_l']:g} L" if car.get("engine_l") is not None else None, car.get("engine_evidence")),
            ("Horsepower", f"{car['horsepower']:,.0f} hp" if car.get("horsepower") is not None else None, car.get("horsepower_evidence")),
            ("Top speed", f"{car['top_speed_mph']:,.0f} mph (~{car['top_speed_kmh']:,.0f} km/h)" if car.get("top_speed_mph") is not None else (f"{car['top_speed_kmh']:,.0f} km/h" if car.get("top_speed_kmh") is not None else None), car.get("speed_mph_evidence") or car.get("speed_kmh_evidence")),
            ("0–100 km/h", f"{car['acceleration_0_100_s']:g} s" if car.get("acceleration_0_100_s") is not None else None, car.get("acceleration_evidence")),
            ("Regional specification", car.get("regional_spec"), None),
            ("Condition", car.get("condition"), car.get("condition_evidence")),
        ]
        lines = []
        for label, value, evidence in known:
            if value is not None:
                add(label, value, evidence)
        snippets = _source_snippets(car, q, limit=10)
        # For a true "everything/full details" request there may be no query
        # keyword to anchor a snippet. In that case expose the listing's retained
        # source facts rather than silently dropping them.
        if not snippets:
            snippets = car.get("key_facts", [])[:10]
        if snippets:
            lines.append("**Other verified details from the listing:**")
            lines.extend([f"• {x}" for x in snippets])

    # Arbitrary description facts, with structured extraction used first so
    # follow-up questions do not accidentally launch a new inventory search.
    special = any(x in q for x in ["transmission", "gear", "feature", "equipment", "colour", "color", "interior", "exterior", "service", "owner", "fuel", "torque", "camera", "carplay", "android", "sunroof", "agency", "key", "dealer", "showroom", "accident", "paint", "condition", "drivetrain", "drive type"])
    if special and not broad:
        if "transmission" in q or "gearbox" in q or re.search(r"\bgear\b", q):
            add("Transmission", car.get("transmission"), car.get("transmission_evidence"))
        if "drivetrain" in q or "drive type" in q or re.search(r"\bdrive\b", q):
            add("Drivetrain", car.get("drive_type"), car.get("drive_type_evidence"))
        if "agency" in q and "key" in q:
            if car.get("agency_keys") is True:
                add("Agency keys", "Yes — the listing explicitly states agency key(s).", car.get("agency_keys_evidence"))
            else:
                add("Agency keys", None)
        snippets = _source_snippets(car, q, limit=5)
        # Avoid duplicating evidence when a structured answer already exists.
        if snippets and not ("transmission" in q or "drivetrain" in q or ("agency" in q and "key" in q) or "colour" in q or "color" in q):
            lines.append("**Evidence from the listing:**")
            lines.extend([f"• {x}" for x in snippets])
        elif not lines:
            lines.append("I couldn't verify that detail from the supplied listing.")

    if not lines:
        snippets = _source_snippets(car, q, limit=5)
        if snippets:
            lines.append("**Evidence from the listing:**")
            lines.extend([f"• {x}" for x in snippets])
        else:
            lines.append("I couldn't verify that detail from the supplied listing.")

    return f"For **{car_label(car)} (Listing #{car['listing_id']})**:\n" + "\n".join(lines)

def grounded_answer(message: str, cars: list[dict[str, Any]], parsed: ParsedQuery, user_memory: dict[str, Any], total_count: int | None = None, resume_already_shown: bool = False) -> str:
    if parsed.intent == "general_chat":
        normalized = message.lower().strip()
        if normalized in {"hi","hello","hey"}:
            if user_memory.get("returning_user") and (user_memory.get("max_budget") or user_memory.get("preferences") or user_memory.get("favorite_listing_ids")):
                return f"Welcome back {user_memory.get('name') or ''}! I remember your saved preferences and shortlist. Want to pick up where you left off?".replace("back !","back!")
            return f"Hey {user_memory.get('name') or ''}! I’m your dubizzle Cars assistant. Tell me what you’re looking for and I’ll search the provided inventory.".replace("Hey !","Hey!")
        # Returning-user resume confirmation: show only the latest saved search.
        # This deliberately does not restore/search inventory or alter any
        # existing booking, retrieval, or memory behaviour.
        if normalized in {"yes","yeah","yep","sure","continue"} and user_memory.get("returning_user"):
            # Only the first confirmation after the returning-user greeting should
            # display the saved search. A repeated "yes" must not keep replaying
            # the same resume prompt or trigger inventory retrieval.
            if resume_already_shown:
                return "I can help you continue your car search. What would you like to look for?"
            recent_searches = user_memory.get("recent_searches") or []
            if recent_searches:
                last_search = recent_searches[-1]
                return f"Your last search was **{last_search}**. Would you like to continue from there?"
            return "I don't have a previous search to resume yet. What kind of car are you looking for today?"
        if normalized in {"no","nope","nah"} and user_memory.get("returning_user"):
            return "No problem! What kind of car are you looking for today?"
        if re.fullmatch(r"(?:my name is|call me)\s+[A-Za-z][A-Za-z .'-]{1,39}", message.strip(), re.I):
            return f"Nice to meet you, **{user_memory.get('name')}**. I’ll remember your name for future conversations."
        return "I’m here to help you explore the provided dubizzle Cars inventory, compare listings, save favourites, qualify enquiries, and arrange viewings."
    if parsed.intent == "unknown": return "I can help with dubizzle Cars — searching the provided inventory, comparing cars, remembering preferences, qualifying enquiries, and booking viewing slots. I can’t help with unrelated requests."
    if not cars: return "I checked the provided Excel inventory and couldn’t find a listing matching those constraints. Try relaxing one requirement and I’ll search again."
    if parsed.sort_by in {"oldest", "newest"} and re.search(r"\bwhat\s+year\b|\byear\b", message.lower()):
        chosen = min(cars, key=lambda c: (c["year"], c["listing_id"])) if parsed.sort_by == "oldest" else max(cars, key=lambda c: (c["year"], -c["listing_id"]))
        direction = "oldest" if parsed.sort_by == "oldest" else "newest"
        return f"The **{direction}** matching listing is **{car_label(chosen)} · Listing #{chosen['listing_id']}**, from **{chosen['year']}**."
    if parsed.sort_by in {"lowest_price", "highest_price"}:
        priced = [c for c in cars if c.get("price_aed") is not None]
        if not priced:
            return "I couldn't verify a cash price for any matching listing in the supplied Excel inventory."
        chosen = (min(priced, key=lambda c: (c["price_aed"], c["listing_id"]))
                  if parsed.sort_by == "lowest_price"
                  else max(priced, key=lambda c: (c["price_aed"], -c["listing_id"])))
        direction = "cheapest" if parsed.sort_by == "lowest_price" else "most expensive"
        return f"The **{direction} matching car** is **{car_label(chosen)} · Listing #{chosen['listing_id']} — {money(chosen['price_aed'])}**."
    if len(cars)==1: return _detail_answer(message,cars[0]) if any(w in message.lower() for w in DETAIL_WORDS) else _listing_summary(cars[0])
    total = total_count if total_count is not None else len(cars)
    lead=", ".join(car_label(c) for c in cars[:3]); extra = f" Showing the strongest {len(cars)} below." if total > len(cars) else ""
    return f"I found **{total} matching listings**. The strongest matches include {lead}.{extra} The cards below are grounded in the supplied Excel inventory, including facts extracted directly from each listing description."


def _listing_summary(c: dict[str,Any]) -> str:
    parts=[f"**{car_label(c)}** · Listing #{c['listing_id']}", f"Cash price: {money(c.get('price_aed'))}"]
    if c.get("monthly_aed") is not None: parts.append(f"Monthly payment: AED {c['monthly_aed']:,.0f}")
    parts.append(f"Mileage: {c['mileage_km']:,.0f} km" if c.get("mileage_km") is not None else "Mileage: not stated")
    if c.get("regional_spec"): parts.append(f"Spec: {c['regional_spec']}")
    if c.get("warranty") is not None: parts.append(f"Warranty: {'stated' if c['warranty'] else 'not stated'}")
    return "\n".join(parts)


def wants_all_results(message: str, parsed: ParsedQuery) -> bool:
    m = message.lower().strip()
    if "details" in m or "everything" in m:
        return False
    if re.search(r"\bshow(?: me)?\s+all\s+(?:matching\s+)?(?:cars|listings|matches|results)\b", m):
        return True
    if re.search(r"\bshow(?: me)?\s+all\b", m):
        return bool(parsed.make or parsed.model)
    return False


class Agent:
    def __init__(self): self.inventory=inventory

    def _parse(self,message:str)->ParsedQuery:
        base=deterministic_parse(message,self.inventory)
        if gemini.available:
            data=gemini.parse_query(message,self.inventory.makes,self.inventory.models)
            if data:
                try:
                    parsed=ParsedQuery.model_validate(data)
                    if base.make: parsed.make=base.make
                    if base.model: parsed.model=base.model
                    for field in ("min_year","max_year","min_price_aed","max_price_aed","min_mileage_km","max_mileage_km","sort_by"):
                        v=getattr(base,field)
                        if v is not None: setattr(parsed,field,v)
                    # Deterministic guardrails own high-level intent. The LLM may
                    # enrich an inventory query, but it must never turn a greeting,
                    # booking request, lead request, favourite action, or guardrail
                    # refusal into an inventory search.
                    if base.intent in {"general_chat", "unknown", "booking", "lead", "favorite"}:
                        return base
                    parsed.ordinal=base.ordinal; parsed.listing_id=base.listing_id; parsed.keywords=list(dict.fromkeys(parsed.keywords+base.keywords))
                    parsed.requires_gcc = bool(parsed.requires_gcc or base.requires_gcc)
                    parsed.requires_warranty = bool(parsed.requires_warranty or base.requires_warranty)
                    # Ranking words are instructions, not searchable text.
                    parsed.keywords=[k for k in parsed.keywords if k.strip().lower() not in {"newest","latest","oldest","cheapest","lowest price","lowest mileage"}]
                    return parsed
                except Exception: pass
        return base

    def chat(self,user_id:str,session_id:str|None,message:str)->dict[str,Any]:
        existing=db.get_profile(user_id); first_seen=not bool(existing.get("created_at"))
        sid=db.get_or_create_session(user_id,session_id); db.ensure_user(user_id)
        previous=db.user_memory(user_id); previous["returning_user"]=not first_seen
        db.add_message(user_id,sid,"user",message)
        name_match = re.fullmatch(r"(?:my name is|call me)\s+([A-Za-z][A-Za-z .'-]{1,39})", message.strip(), re.I)
        if name_match:
            db.update_profile(user_id, name=name_match.group(1).strip())
            previous=db.user_memory(user_id); previous["returning_user"]=not first_seen
        parsed=self._parse(message); pending=db.get_pending_action(sid)

        # A pending booking owns the next booking-specific turn.  Natural
        # datetime replies such as "Saturday at 4 PM" contain no car/inventory
        # vocabulary, so the parser correctly treats them as unknown when
        # considered in isolation.  While a booking draft is active, however,
        # a day/time reply must continue that booking rather than hitting the
        # generic guardrail.  Keep the stored listing_id authoritative.
        if pending.get("type") == "booking":
            pending_date_probe, pending_time_probe = parse_booking_date_time(message)
            if pending_date_probe or pending_time_probe:
                parsed.intent = "booking"
                if pending.get("listing_id") is not None:
                    parsed.listing_id = int(pending["listing_id"])

        # A pending lead owns the next lead-collection turn. Natural replies
        # such as "50-300k", "GCC with warranty", or a name/phone contain no
        # explicit lead keyword, so the parser may otherwise classify them as
        # unknown/inventory. Keep the lead draft alive until it is confirmed.
        if pending.get("type") == "lead":
            if re.search(r"\b(cancel|never mind|nevermind)\b", message.lower()):
                db.set_pending_action(sid, None)
                pending = {}
            else:
                parsed.intent = "lead"
        elif parsed.intent=="inventory_search" and re.search(r"\b(confirm|yes|go ahead|book it|submit)\b",message.lower()):
            if pending.get("type")=="booking": parsed.intent="booking"
            elif pending.get("type")=="lead": parsed.intent="lead"

        # A booking draft is only continued by a booking-specific continuation
        # (date/time, ordinal, or an explicitly named car). A normal inventory
        # or detail query cancels the draft so it cannot hijack later turns.
        if pending.get("type") == "booking" and parsed.intent == "inventory_search":
            pending_date_probe, pending_time_probe = parse_booking_date_time(message)
            booking_words = re.search(r"\b(book|booking|viewing|test\s*drive|appointment)\b", message.lower())
            # An explicit car reference is still part of the booking flow.
            # For example: "I want to book" -> "2024 Mercedes GLS" ->
            # "Sunday at 10 AM". Do NOT cancel the pending booking merely
            # because the car-selection turn is parsed as an inventory search.
            explicit_car = bool(
                parsed.listing_id is not None
                or parsed.make
                or parsed.model
                or parsed.min_year is not None
                or parsed.max_year is not None
            )
            # Only use an explicit car as the response to "which car?" when
            # the pending booking still has no vehicle. Once a vehicle is
            # already selected, a new search such as "Show me BMWs" must
            # cancel that draft rather than hijacking the booking flow.
            selecting_car_for_pending_booking = (
                pending.get("listing_id") is None
                and bool(
                    parsed.listing_id is not None
                    or parsed.model
                    or parsed.min_year is not None
                    or parsed.max_year is not None
                )
            )
            if (not pending_date_probe and not pending_time_probe
                    and parsed.ordinal is None
                    and not booking_words
                    and not selecting_car_for_pending_booking):
                db.set_pending_action(sid, None)
                pending = {}

        # Booking owns its vehicle context. Never silently book the current
        # primary listing from an unrelated inventory result.
        if pending.get("type") == "booking" and parsed.intent == "inventory_search":
            pending_date, pending_time = parse_booking_date_time(message)
            if pending_date or pending_time:
                parsed.intent = "booking"
            elif parsed.ordinal is not None:
                state_for_booking = db.get_session_state(sid)
                ids_for_booking = state_for_booking.get("active_listing_ids", [])
                if 1 <= parsed.ordinal <= len(ids_for_booking):
                    parsed.intent = "booking"
                    parsed.listing_id = int(ids_for_booking[parsed.ordinal - 1])
            elif parsed.listing_id is not None:
                parsed.intent = "booking"
            elif parsed.make or parsed.model or parsed.min_year is not None or parsed.max_year is not None:
                candidates = self.inventory.search(parsed)
                if len(candidates) == 1:
                    parsed.intent = "booking"
                    parsed.listing_id = int(candidates[0]["listing_id"])
                else:
                    # If the user explicitly names a car but the wording is
                    # ambiguous (e.g. "Mercedes GLS" has multiple years),
                    # prefer the already-focused listing when it satisfies
                    # the explicit constraints. Do not fall back to a random
                    # first inventory result.
                    focused = db.get_session_state(sid).get("focused_listing_id")
                    if focused:
                        focused_car = self.inventory.get(int(focused))
                        if focused_car:
                            matches = True
                            if parsed.make and focused_car.get("make") != parsed.make: matches = False
                            if parsed.model and focused_car.get("model") != parsed.model: matches = False
                            if parsed.min_year is not None and focused_car.get("year") < parsed.min_year: matches = False
                            if parsed.max_year is not None and focused_car.get("year") > parsed.max_year: matches = False
                            if matches:
                                parsed.intent = "booking"
                                parsed.listing_id = int(focused_car["listing_id"])

        active_id=context_listing(user_id,sid,parsed,message)

        # For a new booking, resolve an explicitly named car from the Excel
        # inventory instead of inheriting the previous focused listing. If the
        # wording is ambiguous, leave the car unset and let the booking flow ask
        # the user to choose rather than guessing.
        if parsed.intent == "booking" and active_id is None and not db.get_pending_action(sid).get("type") == "booking":
            has_explicit_car = bool(
                parsed.listing_id is not None
                or parsed.make
                or parsed.model
                or parsed.min_year is not None
                or parsed.max_year is not None
            )
            if has_explicit_car:
                candidates = self.inventory.search(parsed)
                if len(candidates) == 1:
                    active_id = int(candidates[0]["listing_id"])
                    parsed.listing_id = active_id
                elif len(candidates) > 1:
                    # An explicit but ambiguous car reference may safely use the
                    # currently focused listing only when that listing satisfies
                    # every explicit constraint (e.g. focused 2024 GLS +
                    # "Book the Mercedes GLS on Sunday"). Never choose the first
                    # search result merely because it happens to be first.
                    focused = db.get_session_state(sid).get("focused_listing_id")
                    focused_car = self.inventory.get(int(focused)) if focused else None
                    if focused_car:
                        matches = True
                        if parsed.make and focused_car.get("make") != parsed.make: matches = False
                        if parsed.model and focused_car.get("model") != parsed.model: matches = False
                        if parsed.min_year is not None and focused_car.get("year") < parsed.min_year: matches = False
                        if parsed.max_year is not None and focused_car.get("year") > parsed.max_year: matches = False
                        if matches:
                            active_id = int(focused_car["listing_id"])
                            parsed.listing_id = active_id

        # Once a booking draft exists, its listing is authoritative for every
        # subsequent date/time turn. This prevents an old focused car from
        # hijacking the booking.
        if pending.get("type") == "booking" and parsed.intent == "booking" and not parsed.listing_id:
            active_id = int(pending.get("listing_id")) if pending.get("listing_id") is not None else active_id
        if parsed.intent == "booking" and active_id is None and not parsed.listing_id:
            candidates = self.inventory.search(parsed)
            if len(candidates) == 1:
                active_id = int(candidates[0]["listing_id"])
        state=db.get_session_state(sid)
        contextual = bool(active_id and parsed.intent=="inventory_search" and not is_inventory_wide_attribute_query(message) and (
            parsed.ordinal is not None
            or re.search(r"\b(it|that car|this car|the car|that one|this one|the same car|same car)\b", message.lower())
            or any(w in message.lower() for w in DETAIL_WORDS)
        ))
        show_all = wants_all_results(message, parsed)
        if show_all and (parsed.make or parsed.model):
            parsed.limit = 20
        cars=[]; booking=None; lead=None; total_count=0
        if parsed.intent in {"general_chat", "unknown"}:
            # Look only at the immediately preceding assistant turn. This keeps
            # the resume behaviour session-local and does not touch long-term
            # memory or inventory retrieval.
            prior_turns = db.recent_messages(sid, limit=2)
            resume_already_shown = (
                parsed.intent == "general_chat"
                and message.lower().strip() in {"yes", "yeah", "yep", "sure", "continue"}
                and any(
                    str(t.get("role", "")).lower() == "assistant"
                    and "Your last search was **" in str(t.get("content", ""))
                    for t in prior_turns
                )
            )
            response = grounded_answer(message, [], parsed, previous, 0, resume_already_shown)
            cars = []
            total_count = 0
        elif parsed.intent=="booking": response,booking,cars=booking_response(user_id,sid,message,active_id)
        elif parsed.intent=="lead": response,lead,cars=lead_response(user_id,sid,message,active_id)
        elif parsed.intent=="favorite":
            if active_id:
                db.favorite(user_id,active_id); car=self.inventory.get(active_id); cars=[car] if car else []
                response=f"Saved **{car_label(car)}** to your favourites. I’ll remember it when you return." if car else "I couldn't resolve that car."
            else:
                cars=[self.inventory.get(i) for i in db.get_favorites(user_id)]; cars=[c for c in cars if c]
                response="Here are the cars you've saved across conversations." if cars else "You don't have any saved cars yet."
        elif contextual:
            car=self.inventory.get(active_id); cars=[car] if car else []; total_count=1 if car else 0
            if car and (parsed.ordinal is not None or re.search(r"\b(it|that car|this car|the car|that one|this one|the same car|same car)\b", message.lower())):
                db.set_focused_listing(sid, car["listing_id"])
            response=grounded_answer(message,cars,parsed,previous,total_count)
        elif show_all and state.get("active_listing_ids") and not (parsed.make or parsed.model):
            all_ids=[int(i) for i in state.get("active_listing_ids",[]) ]
            cars=[self.inventory.get(i) for i in all_ids]; cars=[c for c in cars if c]
            total_count=len(cars)
            response=f"Here are all **{total_count} matching listings** from the supplied Excel inventory."
        else:
            cars=self.inventory.search(parsed); total_count=self.inventory.search_count(parsed); response=grounded_answer(message,cars,parsed,previous,total_count)

        # Keep the complete matching ID set in short-term memory, even when the UI
        # only renders the strongest 8 cards. This lets later ordinal/detail questions
        # resolve against the full result set.
        if parsed.intent=="inventory_search" and not contextual:
            all_ids = self.inventory.search_ids(parsed)
            db.set_session_state(sid,all_ids,parsed.intent,focused_listing_id=(all_ids[0] if all_ids else None))
        if parsed.min_price_aed is not None or parsed.max_price_aed is not None: db.update_profile(user_id,min_budget=parsed.min_price_aed,max_budget=parsed.max_price_aed)
        if parsed.intent == "inventory_search":
            bits=[]
            if parsed.make: bits.append(parsed.make.title())
            if parsed.model: bits.append(parsed.model.title())
            if parsed.min_year is not None and parsed.max_year is not None and parsed.min_year == parsed.max_year: bits.append(str(parsed.min_year))
            elif parsed.min_year is not None: bits.append(f"from {parsed.min_year}")
            elif parsed.max_year is not None: bits.append(f"up to {parsed.max_year}")
            if parsed.min_price_aed is not None and parsed.max_price_aed is not None: bits.append(f"AED {parsed.min_price_aed:,.0f}–{parsed.max_price_aed:,.0f}")
            elif parsed.max_price_aed is not None: bits.append(f"under AED {parsed.max_price_aed:,.0f}")
            elif parsed.min_price_aed is not None: bits.append(f"from AED {parsed.min_price_aed:,.0f}")
            if parsed.max_mileage_km is not None: bits.append(f"under {parsed.max_mileage_km:,.0f} km")
            if parsed.requires_gcc: bits.append("GCC")
            if parsed.requires_warranty: bits.append("with warranty")
            if parsed.sort_by == "newest": bits.append("newest")
            elif parsed.sort_by == "oldest": bits.append("oldest")
            elif parsed.sort_by == "lowest_price": bits.append("cheapest")
            elif parsed.sort_by == "lowest_mileage": bits.append("lowest mileage")
            bits.extend([k for k in parsed.keywords[:6] if k not in {"gcc", "warranty"}])
            if bits:
                db.append_preference(user_id, ", ".join(bits))
        memory=db.user_memory(user_id); memory["returning_user"]=not first_seen
        state=db.get_session_state(sid); recent=db.recent_messages(sid,limit=8)
        memory["short_term"]={"active_listing_ids":state.get("active_listing_ids",[]),"focused_listing_id":state.get("focused_listing_id"),"recent_turns":len(recent),"last_intent":state.get("last_intent","")}
        memory["long_term"]={"name":memory.get("name"),"budget":{"min":memory.get("min_budget"),"max":memory.get("max_budget")},"preferences":memory.get("preferences",""),"recent_searches":memory.get("recent_searches",[]),"favorite_listing_ids":memory.get("favorite_listing_ids",[])}
        db.add_message(user_id,sid,"assistant",response)
        return {"user_id":user_id,"session_id":sid,"response":response,"intent":parsed.intent,"matched_cars":cars,"total_matches":total_count if total_count else len(cars),"memory":memory,"booking":booking,"lead":lead,"meta":{"llm_enabled":gemini.available,"grounded":True,"dataset_rows":len(self.inventory.df),"source":"provided Excel only"}}

agent=Agent()

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any

import pandas as pd

from .config import settings


def clean_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines()]
    return "\n".join(x for x in lines if x)


def flat_text(value: Any) -> str:
    return re.sub(r"\s+", " ", clean_text(value)).strip()


def _number(value: str) -> float:
    return float(value.replace(",", "").replace(" ", ""))


def _evidence(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -:•|/")


def _finance_context(text: str, start: int, end: int) -> bool:
    ctx = text[max(0, start - 45): min(len(text), end + 65)].lower()
    return bool(re.search(
        r"monthly|per\s+month|/\s*mo\b|\bpm\b|down[- ]?payment|installment|finance|financing|insurance|registration",
        ctx,
        re.I,
    ))


def extract_cash_price(title: str, description: str) -> tuple[float | None, str | None]:
    """Find the listing's cash/asking price from title/description only."""
    sources = [description, title]

    # Explicit cash / sale price always wins over finance figures.
    explicit_cash = [
        r"(?:AED|DHS|DH)\s*(?P<amount>[\d,]+(?:\.\d+)?)\s*(?:/-)?\s*(?:in\s+cash|cash|cash\s+price)\b",
        r"(?P<amount>[\d,]+(?:\.\d+)?)\s*(?:AED|DHS|DH)\s*(?:/-)?\s*(?:in\s+cash|cash)\b",
        r"(?:cash\s+price|asking\s+price)\s*(?:is|:|-)?\s*(?:AED|DHS|DH)?\s*(?P<amount>[\d,]+(?:\.\d+)?)",
    ]
    for text in sources:
        for pattern in explicit_cash:
            m = re.search(pattern, text, re.I)
            if m:
                v = _number(m.group("amount"))
                if 3_000 <= v <= 10_000_000:
                    return v, _evidence(m.group(0))

    # Common pattern: 1,349,999 AED / 25,683 AED per Month.
    for text in sources:
        m = re.search(
            r"(?P<amount>[\d,]+(?:\.\d+)?)\s*(?:AED|DHS|DH)\s*/\s*[\d,]+(?:\.\d+)?\s*(?:AED|DHS|DH)\s*(?:per\s+month|monthly|/\s*month)",
            text,
            re.I,
        )
        if m:
            v = _number(m.group("amount"))
            if 3_000 <= v <= 10_000_000:
                return v, _evidence(m.group(0).split("/")[0])

    # Explicit price/payment labels. "Payment: AED 54,500" is treated as the
    # asking price unless that local phrase clearly says monthly/finance.
    labelled = [
        r"(?:price|payment|price\s+reduced|price\s+drop|price\s*#)\s*(?:is|:|-|#)?\s*(?:AED|DHS|DH)?\s*(?P<amount>[\d,]+(?:\.\d+)?)\s*(?:AED|DHS|DH)?",
        r"(?:AED|DHS|DH)\s*(?P<amount>[\d,]+(?:\.\d+)?)\s*(?:for\s+sale|asking\s+price)\b",
    ]
    for text in sources:
        for pattern in labelled:
            for m in re.finditer(pattern, text, re.I):
                v = _number(m.group("amount"))
                if 3_000 <= v <= 10_000_000:
                    # Labelled price/payment amounts are trusted unless the
                    # amount itself is immediately described as monthly.
                    after = text[m.end():m.end()+35]
                    before = text[max(0,m.start()-25):m.start()]
                    if not re.search(r"monthly|per\s+month|/\s*mo\b|\bpm\b|installment", after, re.I) and not re.search(r"monthly|installment", before, re.I):
                        return v, _evidence(m.group(0))

    # Generic currency amount. Ignore monthly/installment/down-payment contexts.
    currency = r"(?:AED|DHS|DH)\s*(?P<a>[\d,]+(?:\.\d+)?)\b|(?P<b>[\d,]+(?:\.\d+)?)\s*(?:AED|DHS|DH)\b"
    for text in sources:
        for m in re.finditer(currency, text, re.I):
            raw = m.group("a") or m.group("b")
            v = _number(raw)
            if 3_000 <= v <= 10_000_000 and not _finance_context(text, m.start(), m.end()):
                return v, _evidence(m.group(0))

    return None, None


def _speed_context(text: str, start: int, end: int) -> bool:
    ctx = text[max(0, start - 80): min(len(text), end + 40)].lower()
    return bool(re.search(r"max(?:imum)?\s+speed|top\s+speed|\bspeed\b|km\s*/\s*h|mph", ctx))


def extract_mileage(title: str, description: str) -> tuple[float | None, str | None]:
    """Extract actual vehicle mileage, never km/h or service/warranty mileage."""
    sources = [description, title]
    strong = [
        r"(?:mileage|odometer)\s*(?:is|:|-)?\s*(?P<a>[\d,]+(?:\s+[\d,]+)?)\s*(?:km|kms|kilometers?|kilometres?)\b",
        r"(?:done|done\s+only|only)\s*(?P<a>[\d,]+(?:\s+[\d,]+)?)\s*(?:km|kms|kilometers?|kilometres?)\b",
    ]
    for text in sources:
        for pattern in strong:
            m = re.search(pattern, text, re.I)
            if m:
                v = _number(m.group("a"))
                if not _speed_context(text, m.start(), m.end()):
                    return v, _evidence(m.group(0))

    # Generic mileage. Do NOT allow whitespace to join adjacent fields such as
    # "MODEL 2024 11,000 KM" into the fake value 202411000. Support either
    # comma-grouped numbers or ordinary integers.
    generic = r"(?P<a>(?:\d{1,3}(?:,\d{3})+|\d+))\s*(?:km|kms|kilometers?|kilometres?)\b"
    for text in sources:
        for m in re.finditer(generic, text, re.I):
            v = _number(m.group("a"))
            after = text[m.end():m.end()+10].lower()
            ctx = text[max(0, m.start()-90):min(len(text), m.end()+90)].lower()
            if re.match(r"\s*/\s*h\b", after) or _speed_context(text, m.start(), m.end()):
                continue
            # A mileage candidate immediately preceded by a model year is still
            # valid (e.g. "2021 71000 KM"), but the year itself must never be
            # concatenated with the mileage.
            if re.search(r"last\s+service|next\s+service|service\s+history|warranty.{0,25}km|up\s+to\s+[\d,]+\s*km", ctx):
                continue
            if re.search(r"0\s*(?:to|-|–)\s*100\s*km", ctx):
                continue
            if 0 <= v <= 1_000_000:
                return v, _evidence(m.group(0))
    return None, None


def extract_top_speed(text: str) -> tuple[float | None, str | None, float | None, str | None]:
    mph = kmh = None
    mph_ev = kmh_ev = None
    combined = re.search(
        r"(?:max(?:imum)?\s+speed|top\s+speed).*?(?P<mph>[\d,]+(?:\.\d+)?)\s*mph\s*/\s*(?P<kmh>[\d,]+(?:\.\d+)?)\s*km\s*/\s*h",
        text, re.I,
    )
    if combined:
        mph = _number(combined.group("mph")); kmh = _number(combined.group("kmh"));
        mph_ev = _evidence(combined.group(0)); kmh_ev = mph_ev
    if mph is None:
        m = re.search(r"(?:max(?:imum)?\s+speed|top\s+speed)\s*(?:is|:|-)?\s*(?P<v>[\d,]+(?:\.\d+)?)\s*mph", text, re.I)
        if m:
            mph = _number(m.group("v")); mph_ev = _evidence(m.group(0))
    if kmh is None:
        m = re.search(r"(?:max(?:imum)?\s+speed|top\s+speed)\s*(?:is|:|-)?\s*(?P<v>[\d,]+(?:\.\d+)?)\s*(?:km\s*/\s*h|kmh)", text, re.I)
        if m:
            kmh = _number(m.group("v")); kmh_ev = _evidence(m.group(0))
    # Also support a standalone km/h figure when the nearby text says speed.
    if kmh is None:
        for m in re.finditer(r"(?P<v>[\d,]+(?:\.\d+)?)\s*km\s*/\s*h", text, re.I):
            if _speed_context(text, m.start(), m.end()):
                kmh = _number(m.group("v")); kmh_ev = _evidence(m.group(0)); break
    if kmh is None and mph is None:
        return None, None, None, None
    normalized = kmh if kmh is not None else round(mph * 1.609344, 1)
    return normalized, kmh_ev, mph, mph_ev


def extract_horsepower(text: str) -> tuple[float | None, str | None]:
    for p in [r"(?P<a>[\d,]+(?:\.\d+)?)\s*(?:horsepower|bhp|hp)\b", r"horsepower\s*(?:is|:|-)?\s*(?P<a>[\d,]+(?:\.\d+)?)\b"]:
        m = re.search(p, text, re.I)
        if m:
            return _number(m.group("a")), _evidence(m.group(0))
    return None, None


def extract_engine_l(text: str) -> tuple[float | None, str | None]:
    # Preserve the useful descriptor immediately attached to the engine size,
    # e.g. "2.0 L + Turbo" or "3.0L turbocharged inline-6 engine".
    patterns = [
        r"\b(?P<a>\d+(?:\.\d+)?)\s*[Ll]\s*(?:turbocharged?|supercharged?)(?:\s+inline-?\d+)?\s+engine\b",
        r"\b(?P<a>\d+(?:\.\d+)?)\s*[Ll](?:\s*\+\s*(?:turbo|turbocharged|supercharged))?\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.I)
        if m:
            return float(m.group("a")), _evidence(m.group(0))
    return None, None


def extract_acceleration_0_100(text: str) -> tuple[float | None, str | None]:
    patterns = [
        r"0\s*(?:to|-|–)\s*100\s*km\s*/\s*h[^\d]{0,40}(?:in|approximately|→|➔)\s*(?P<a>\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)",
        r"0\s*(?:to|-|–)\s*100[^\d]{0,40}(?:in|approximately|→|➔)\s*(?P<a>\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m: return float(m.group("a")), _evidence(m.group(0))
    return None, None


def extract_monthly(text: str) -> tuple[float | None, str | None]:
    patterns = [
        r"(?:AED|DHS|DH)\s*(?P<a>[\d,]+(?:\.\d+)?)\s*(?:/|per\s*)month",
        r"(?P<a>[\d,]+(?:\.\d+)?)\s*(?:AED|DHS|DH)\s*(?:/|per\s*)month",
        r"(?:AED|DHS|DH)\s*(?P<a>[\d,]+(?:\.\d+)?)\s*(?:/\s*mo|per\s+month|monthly)",
        # Currency + PM is accepted only when it is clearly a payment,
        # avoiding showroom times such as "After 8PM Dubai".
        r"(?:AED|DHS|DH)\s*(?P<a>[\d,]+(?:\.\d+)?)\s*(?:pm|p\.m\.)\b",
        r"(?P<a>[\d,]+(?:\.\d+)?)\s*(?:AED|DHS|DH)\s*(?:pm|p\.m\.)\b",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            # Do not mistake showroom clock times such as 10:00PM for a
            # monthly payment.
            before = text[max(0, m.start()-4):m.start()]
            if re.search(r"\d{1,2}:$", before):
                continue
            return _number(m.group("a")), _evidence(m.group(0))
    return None, None


def extract_transmission(text: str) -> tuple[str | None, str | None]:
    """Extract an explicit transmission/gearbox statement from the listing."""
    # Prefer named gearboxes such as 9G-TRONIC before generic "automatic".
    named = [
        r"(?P<v>\btransmission\s*:\s*[^.;|•]{2,70})",
        r"(?P<v>\b(?:9G-TRONIC|8G-TRONIC|7G-TRONIC|PDK|DSG)\b[^.;|]{0,70}(?:transmission|gearbox|gear)\b)",
        r"(?P<v>\b\d+\s*-?\s*speed\s+(?:dual\s+clutch|automatic|manual)[^.;|]{0,50}(?:transmission|gearbox|gear)\b)",
        r"(?P<v>\b(?:dual\s+clutch|dct|automatic|manual|tiptronic|cvt)[^.;|]{0,80}(?:transmission|gearbox|gear)\b)",
    ]
    for p in named:
        m = re.search(p, text, re.I)
        if m:
            value = _evidence(m.group("v"))
            value = re.sub(r"^transmission\s*:\s*", "", value, flags=re.I)
            return value, _evidence(m.group("v"))

    m = re.search(r"\b(\d+)\s+auto\s+speed\s+gearbox\b", text, re.I)
    if m:
        return f"{m.group(1)}-speed automatic gearbox", _evidence(m.group(0))

    # Arabic listing shorthand used in the supplied BMW X1 description:
    # "8 سرعات القير الأوتوماتيكي" = 8-speed automatic gearbox.
    m = re.search(r"\b(\d+)\s*سرعات?\s+(?:القير|ناقل الحركة)\s*(?:الأوتوماتيكي|اوتوماتيك|الأتوماتيكي)?\b", text, re.I)
    if m:
        return f"{m.group(1)}-speed automatic gearbox", _evidence(m.group(0))
    return None, None


def extract_drive_type(text: str) -> tuple[str | None, str | None]:
    patterns = [
        (r"\b(4MATIC\s+all-?wheel\s+drive)\b", "AWD"),
        (r"\b(all-?wheel\s+drive|AWD)\b", "AWD"),
        (r"\b(four-?wheel\s+drive|4WD)\b", "4WD"),
        (r"\b(front-?wheel\s+drive|FWD)\b", "FWD"),
        (r"\b(rear-?wheel\s+drive|RWD)\b", "RWD"),
    ]
    for p, label in patterns:
        m = re.search(p, text, re.I)
        if m:
            return label, _evidence(m.group(0))
    return None, None


def extract_agency_keys(text: str) -> tuple[bool | None, str | None]:
    m = re.search(r"\b(two|2)\s+agency\s+keys?\b", text, re.I)
    if m:
        return True, _evidence(m.group(0))
    m = re.search(r"\b(?:one|1)\s+agency\s+key\b", text, re.I)
    if m:
        return True, _evidence(m.group(0))
    if re.search(r"\bagency\s+keys?\b", text, re.I):
        return True, _evidence(re.search(r"\bagency\s+keys?\b", text, re.I).group(0))
    return None, None

def extract_exterior_colour(text: str) -> tuple[str | None, str | None]:
    """Extract an explicitly stated exterior/body colour from source text."""
    patterns = [
        r"(?:exterior|body)\s*(?:colour|color)\s*[:\-]?\s*(?P<v>[a-zA-Z][a-zA-Z /-]{2,30})",
        r"(?P<v>white|black|red|blue|silver|grey|gray|beige|brown|green|gold|yellow|orange|purple)\s+(?:exterior|body)",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            value = _evidence(m.group("v"))
            value = re.split(r"\b(?:interior|model|year|mileage|spec|gcc|usa|price|aed)\b", value, flags=re.I)[0].strip(" ,;:-")
            if value:
                return value.title(), _evidence(m.group(0))
    # Common listing style: "1. Silver with Fabric interior". Only accept it
    # when a colour word is directly tied to the vehicle details, not arbitrary
    # prose later in the description.
    m = re.search(r"(?:^|[.;|])\s*(?:\d+\.\s*)?(?P<v>white|black|red|blue|silver|grey|gray|beige|brown|green|gold|yellow|orange|purple)\s+(?:with|exterior|body)\b", text, re.I)
    if m:
        return m.group("v").title(), _evidence(m.group(0))
    return None, None

def extract_body_type(text: str) -> str | None:
    checks = [("convertible", ["convertible", "volante"]), ("coupe", ["coupe"]), ("suv", ["suv", "sport utility"]), ("sedan", ["sedan", "saloon"]), ("hatchback", ["hatchback"]), ("pickup", ["pickup", "pick-up"]), ("wagon", ["wagon"])]
    t = text.lower()
    for label, words in checks:
        if any(w in t for w in words): return label
    return None


def extract_spec(text: str) -> str | None:
    checks = [
        ("GCC", r"\bgcc\b"),
        ("USA", r"\b(?:usa|american|us spec|u\.s\. spec)\b"),
        ("European", r"\beuropean\b"),
        ("Japanese", r"\bjapanese\b"),
        ("Korea", r"\b(?:korea|korean)(?:\s+spec(?:ifications?)?)?\b"),
    ]
    t = text.lower()
    for label, p in checks:
        if re.search(p, t): return label
    return None


def extract_warranty(text: str) -> bool | None:
    """Return warranty status only when the listing explicitly states one.

    "warranty can be arranged" is deliberately treated as unknown rather than
    as an included warranty; it is an optional service, not a vehicle fact.
    """
    t = text.lower()
    if "warranty" not in t:
        return None
    if re.search(r"(?:no|without)\s+warranty|warranty[^.]{0,30}(?:expired|none)", t, re.I):
        return False
    if re.search(r"warranty\s+can\s+be\s+arranged", t, re.I):
        # Continue searching: a listing can mention an optional warranty in
        # boilerplate and also state a real warranty elsewhere.
        explicit = re.sub(r"warranty\s+can\s+be\s+arranged", "", t, flags=re.I)
        if "warranty" not in explicit:
            return None
        t = explicit
    return True


def extract_condition(text: str) -> tuple[str | None, str | None]:
    """Extract explicit accident/paint condition statements from source text."""
    patterns = [
        r"completely\s+free\s+of\s+paint,\s*accidents(?:\s+and)?\s+scratches",
        r"no\s+accidents?\s*,?\s*no\s+repaints?",
        r"free\s+accident",
        r"accident[- ]?free",
        r"original\s+paint",
        r"no\s+repaints?",
    ]
    matches=[]
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            val=_evidence(m.group(0))
            if val and val.lower() not in {x.lower() for x in matches}:
                matches.append(val)
    if not matches:
        return None, None
    # Prefer a combined statement when the source explicitly provides one.
    if len(matches) == 1:
        return matches[0], matches[0]
    combined = "; ".join(matches[:3])
    return combined, combined

def extract_zero_km(text: str) -> bool:
    return bool(re.search(r"\b0\s*km\b|\bzero\s*km\b|\bbrand new\b|\bnew\s+car\b", text, re.I))


def extract_key_facts(description: str, title: str = "") -> list[str]:
    """Keep useful source phrases so arbitrary description facts remain retrievable."""
    raw = flat_text(description)
    pieces = re.split(r"\s*•\s*|\s*\|\s*|(?<=[.!?])\s+", raw)
    out: list[str] = []
    seen = set()
    for piece in pieces:
        p = re.sub(r"\s+", " ", piece).strip(" -:;")
        if len(p) < 4: continue
        key = p.lower()
        if key in seen: continue
        seen.add(key)
        # Keep facts, not generic contact/marketing boilerplate.
        if re.search(r"(?:model|spec|mileage|km|price|aed|warranty|engine|power|hp|bhp|torque|transmission|gear|fuel|color|colour|interior|exterior|drive|awd|4wd|service|owner|sunroof|camera|carplay|android|leather|registration|insurance|condition|accident|accidents|paint|repaint|agency|keys|dealer|showroom|speed|acceleration|year)", p, re.I):
            out.append(p)
    return out[:40]


@dataclass
class Inventory:
    df: pd.DataFrame

    def __init__(self, path: str | None = None):
        source = path or settings.dataset_path
        df = pd.read_excel(source, sheet_name="cleaned dataset")
        required = {"Listing_ID", "year", "make", "model", "trim", "title", "description", "photo_url"}
        missing = required - set(df.columns)
        if missing: raise ValueError(f"Dataset is missing required columns: {sorted(missing)}")
        df = df[df["Listing_ID"].notna()].copy()
        df["make"] = df["make"].fillna("").astype(str).str.strip().str.lower()
        df["model"] = df["model"].fillna("").astype(str).str.strip().str.lower()
        df["trim"] = df["trim"].fillna("").astype(str).str.strip()
        df["title"] = df["title"].fillna("").astype(str)
        df["description"] = df["description"].fillna("").astype(str)
        df["photo_url"] = df["photo_url"].fillna("").astype(str)
        df["text"] = (df["title"] + "\n" + df["description"]).map(flat_text)
        df["text_lower"] = df["text"].str.lower()

        cash = [extract_cash_price(t, d) for t, d in zip(df["title"], df["description"])]
        mileage = [extract_mileage(t, d) for t, d in zip(df["title"], df["description"])]
        speed = [extract_top_speed(flat_text(t + " " + d)) for t, d in zip(df["title"], df["description"])]
        horsepower = [extract_horsepower(flat_text(t + " " + d)) for t, d in zip(df["title"], df["description"])]
        engine = [extract_engine_l(flat_text(t + " " + d)) for t, d in zip(df["title"], df["description"])]
        acceleration = [extract_acceleration_0_100(flat_text(t + " " + d)) for t, d in zip(df["title"], df["description"])]
        monthly = [extract_monthly(flat_text(t + " " + d)) for t, d in zip(df["title"], df["description"])]
        transmission = [extract_transmission(flat_text(t + " " + d)) for t, d in zip(df["title"], df["description"])]
        drive_type = [extract_drive_type(flat_text(t + " " + d)) for t, d in zip(df["title"], df["description"])]
        agency_keys = [extract_agency_keys(flat_text(t + " " + d)) for t, d in zip(df["title"], df["description"])]

        df["price_aed"] = [x[0] for x in cash]; df["price_evidence"] = [x[1] for x in cash]
        df["monthly_aed"] = [x[0] for x in monthly]; df["monthly_evidence"] = [x[1] for x in monthly]
        df["mileage_km"] = [x[0] for x in mileage]; df["mileage_evidence"] = [x[1] for x in mileage]
        df["top_speed_kmh"] = [x[0] for x in speed]; df["speed_kmh_evidence"] = [x[1] for x in speed]
        df["top_speed_mph"] = [x[2] for x in speed]; df["speed_mph_evidence"] = [x[3] for x in speed]
        df["horsepower"] = [x[0] for x in horsepower]; df["horsepower_evidence"] = [x[1] for x in horsepower]
        df["engine_l"] = [x[0] for x in engine]; df["engine_evidence"] = [x[1] for x in engine]
        df["transmission"] = [x[0] for x in transmission]; df["transmission_evidence"] = [x[1] for x in transmission]
        df["drive_type"] = [x[0] for x in drive_type]; df["drive_type_evidence"] = [x[1] for x in drive_type]
        df["agency_keys"] = [x[0] for x in agency_keys]; df["agency_keys_evidence"] = [x[1] for x in agency_keys]
        df["acceleration_0_100_s"] = [x[0] for x in acceleration]; df["acceleration_evidence"] = [x[1] for x in acceleration]
        df["body_type"] = df["text"].map(extract_body_type); df["regional_spec"] = df["text"].map(extract_spec)
        colours = [extract_exterior_colour(flat_text(t + " " + d)) for t, d in zip(df["title"], df["description"])]
        df["exterior_colour"] = [x[0] for x in colours]; df["exterior_colour_evidence"] = [x[1] for x in colours]
        condition = [extract_condition(flat_text(t + " " + d)) for t, d in zip(df["title"], df["description"])]
        df["condition"] = [x[0] for x in condition]; df["condition_evidence"] = [x[1] for x in condition]
        df["warranty"] = df["text"].map(extract_warranty); df["zero_km"] = df["text"].map(extract_zero_km)
        df["key_facts"] = [extract_key_facts(d, t) for t, d in zip(df["title"], df["description"])]
        self.df = df
        self.makes = sorted(set(df["make"]) - {""}, key=len, reverse=True)
        self.models = sorted(set(df["model"]) - {""}, key=len, reverse=True)

    def summary(self) -> dict[str, Any]:
        return {"total_listings": int(len(self.df)), "year_min": int(self.df["year"].min()), "year_max": int(self.df["year"].max()), "makes": int(self.df["make"].nunique()), "with_cash_price": int(self.df["price_aed"].notna().sum()), "with_mileage": int(self.df["mileage_km"].notna().sum()), "with_top_speed": int(self.df["top_speed_kmh"].notna().sum()), "with_warranty": int(self.df["warranty"].eq(True).sum())}

    def get(self, listing_id: int) -> dict[str, Any] | None:
        rows = self.df[self.df["Listing_ID"] == listing_id]
        return self._serialize(rows.iloc[0]) if not rows.empty else None

    def _serialize(self, row: pd.Series) -> dict[str, Any]:
        def num(v): return None if pd.isna(v) else float(v)
        def val(v): return None if pd.isna(v) else v
        return {
            "listing_id": int(row["Listing_ID"]), "year": int(row["year"]), "make": str(row["make"]), "model": str(row["model"]), "trim": str(row["trim"]),
            "title": flat_text(row["title"]), "description": flat_text(row["description"]), "photo_url": str(row["photo_url"]),
            "price_aed": num(row["price_aed"]), "price_evidence": val(row["price_evidence"]), "monthly_aed": num(row["monthly_aed"]), "monthly_evidence": val(row["monthly_evidence"]),
            "mileage_km": num(row["mileage_km"]), "mileage_evidence": val(row["mileage_evidence"]), "top_speed_kmh": num(row["top_speed_kmh"]), "speed_kmh_evidence": val(row["speed_kmh_evidence"]),
            "top_speed_mph": num(row["top_speed_mph"]), "speed_mph_evidence": val(row["speed_mph_evidence"]), "horsepower": num(row["horsepower"]), "horsepower_evidence": val(row["horsepower_evidence"]),
            "engine_l": num(row["engine_l"]), "engine_evidence": val(row["engine_evidence"]),
            "transmission": val(row["transmission"]), "transmission_evidence": val(row["transmission_evidence"]),
            "drive_type": val(row["drive_type"]), "drive_type_evidence": val(row["drive_type_evidence"]),
            "agency_keys": None if pd.isna(row["agency_keys"]) else bool(row["agency_keys"]), "agency_keys_evidence": val(row["agency_keys_evidence"]),
            "acceleration_0_100_s": num(row["acceleration_0_100_s"]), "acceleration_evidence": val(row["acceleration_evidence"]),
            "body_type": val(row["body_type"]), "exterior_colour": val(row["exterior_colour"]), "exterior_colour_evidence": val(row["exterior_colour_evidence"]), "regional_spec": val(row["regional_spec"]), "condition": val(row["condition"]), "condition_evidence": val(row["condition_evidence"]), "warranty": None if pd.isna(row["warranty"]) else bool(row["warranty"]), "zero_km": bool(row["zero_km"]),
            "key_facts": list(row["key_facts"] or []),
        }

    def _keyword_mask(self, frame: pd.DataFrame, keyword: str) -> pd.Series:
        """Match description/title attributes using verified wording variants."""
        k = keyword.lower().strip()
        text = frame["text_lower"]
        variants = {
            "seven_seat": r"\b7[- ]seat(?:s)?\b|\b7[- ]seater\b|\bseven[- ]seat",
            "panoramic": r"\bpanoramic\b|\bpanorama\b",
            "accident_free": r"accident[- ]?free|free[^.]{0,35}accidents?|no\s+accidents?|without\s+accidents?",
            "turbo": r"\bturbo(?:charged)?\b",
        }
        pattern = variants.get(k, re.escape(k))
        return text.str.contains(pattern, regex=True, na=False)

    def _rank(self, row: pd.Series, query: Any) -> float:
        score = 0.0; text = row["text_lower"]
        if query.make and row["make"] == query.make.lower(): score += 30
        if query.model and row["model"] == query.model.lower(): score += 35
        for k in query.keywords:
            if self._keyword_mask(self.df.loc[[row.name]], k).iloc[0]: score += 8
        if query.sort_by == "newest": score += max(0, int(row["year"]) - 2000) * .2
        elif query.sort_by == "oldest": score += max(0, 2030 - int(row["year"])) * .2
        return score

    def _filtered(self, query: Any) -> pd.DataFrame:
        d = self.df.copy()
        if query.make: d = d[d["make"] == query.make.lower()]
        if query.model: d = d[d["model"] == query.model.lower()]
        if query.min_year is not None: d = d[d["year"] >= query.min_year]
        if query.max_year is not None: d = d[d["year"] <= query.max_year]
        if query.min_price_aed is not None: d = d[d["price_aed"].notna() & (d["price_aed"] >= query.min_price_aed)]
        if query.max_price_aed is not None: d = d[d["price_aed"].notna() & (d["price_aed"] <= query.max_price_aed)]
        if query.min_mileage_km is not None: d = d[d["mileage_km"].notna() & (d["mileage_km"] >= query.min_mileage_km)]
        if query.max_mileage_km is not None: d = d[d["mileage_km"].notna() & (d["mileage_km"] <= query.max_mileage_km)]
        if getattr(query, "requires_gcc", False): d = d[d["regional_spec"].fillna("").str.lower().eq("gcc")]
        if getattr(query, "requires_warranty", False): d = d[d["warranty"].eq(True)]
        for k in query.keywords:
            k = k.lower().strip()
            if k and k not in {"gcc", "warranty"}: d = d[self._keyword_mask(d, k)]
        return d

    def search_count(self, query: Any) -> int:
        return int(len(self._filtered(query)))

    def search_ids(self, query: Any) -> list[int]:
        """Return every matching Listing_ID in the same order as the public search."""
        d = self._filtered(query)
        if d.empty:
            return []
        if query.sort_by == "lowest_price": d = d.sort_values("price_aed", na_position="last")
        elif query.sort_by == "highest_price": d = d.sort_values("price_aed", ascending=False, na_position="last")
        elif query.sort_by == "lowest_mileage": d = d.sort_values("mileage_km", na_position="last")
        elif query.sort_by == "oldest": d = d.sort_values(["year", "Listing_ID"], ascending=[True, True])
        else:
            d = d.assign(_score=d.apply(lambda r: self._rank(r, query), axis=1)).sort_values(["_score", "year", "Listing_ID"], ascending=[False, False, True])
        return [int(x) for x in d["Listing_ID"].tolist()]

    def search(self, query: Any) -> list[dict[str, Any]]:
        d = self._filtered(query)
        if d.empty:
            return []
        if query.sort_by == "lowest_price": d = d.sort_values("price_aed", na_position="last")
        elif query.sort_by == "highest_price": d = d.sort_values("price_aed", ascending=False, na_position="last")
        elif query.sort_by == "lowest_mileage": d = d.sort_values("mileage_km", na_position="last")
        elif query.sort_by == "oldest": d = d.sort_values(["year", "Listing_ID"], ascending=[True, True])
        else:
            d = d.assign(_score=d.apply(lambda r: self._rank(r, query), axis=1)).sort_values(["_score", "year", "Listing_ID"], ascending=[False, False, True])
        limit = max(1, min(int(getattr(query, "limit", settings.max_results)), 20))
        return [self._serialize(row) for _, row in d.head(limit).iterrows()]

    def search_text(self, text: str, limit: int = 8) -> list[dict[str, Any]]:
        terms = [t for t in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(t) >= 3]
        d = self.df.copy(); score = pd.Series(0.0, index=d.index)
        for term in terms: score += d["text_lower"].str.contains(re.escape(term), regex=True, na=False).astype(float)
        d = d.assign(_score=score); d = d[d["_score"] > 0].sort_values(["_score", "year"], ascending=[False, False])
        return [self._serialize(row) for _, row in d.head(limit).iterrows()]


inventory = Inventory()

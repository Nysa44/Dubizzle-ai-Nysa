
from fastapi.testclient import TestClient
from backend.main import app


def test_health():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["inventory_rows"] == 100


def test_new_session_recalls_favorite():
    from backend import db
    db.init_db()
    db.favorite("persistent_test_user", 17)
    with TestClient(app) as client:
        response = client.post("/chat", json={"user_id":"persistent_test_user", "message":"What cars have I saved?"})
        assert response.status_code == 200
        data = response.json()
        assert data["intent"] == "favorite"
        assert 17 in data["memory"]["favorite_listing_ids"]


def test_booking_keeps_selected_listing_for_datetime_turn(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "booking.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    first = a.chat("booking_regression", None, "I want to book a viewing for the 2024 Mercedes GLS")
    assert first["booking"]["status"] == "needs_datetime"
    assert first["booking"]["listing_id"] == 40
    booked = a.chat("booking_regression", first["session_id"], "Saturday at 3 PM")
    assert booked["booking"]["status"] == "confirmed"
    assert booked["booking"]["listing_id"] == 40
    assert "2024 Mercedes-Benz Gls-Class" in booked["response"]


def test_warranty_followup_returns_structured_evidence(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "warranty.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    first = a.chat("warranty_regression", None, "Show me the 2024 Mercedes GLS")
    answer = a.chat("warranty_regression", first["session_id"], "What's the warranty?")
    assert "5 Years Gargash Auto Warranty" in answer["response"]
    assert "Evidence from the listing" not in answer["response"]


def test_bare_booking_does_not_auto_select_focused_car(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "bare_booking.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    first = a.chat("bare_booking_regression", None, "Show me BMWs")
    answer = a.chat("bare_booking_regression", first["session_id"], "I want to book a viewing")
    assert answer["intent"] == "booking"
    assert answer["booking"]["status"] == "needs_car"
    assert "listing_id" not in answer["booking"]
    assert "Which car" in answer["response"]


def test_explicit_booking_still_selects_named_unique_car(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "explicit_booking.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    answer = a.chat("explicit_booking_regression", None, "I want to book a viewing for the 2024 Mercedes GLS")
    assert answer["booking"]["status"] == "needs_datetime"
    assert answer["booking"]["listing_id"] == 40


def test_warranty_remains_source_grounded(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "warranty2.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    first = a.chat("warranty_regression2", None, "Show me the 2024 Mercedes GLS")
    answer = a.chat("warranty_regression2", first["session_id"], "What's the warranty?")
    assert "5 Years Gargash Auto Warranty" in answer["response"]
    assert "Warranty stated" not in answer["response"]


def test_bare_booking_then_ordinal_continues_booking_flow(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "ordinal_booking.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    first = a.chat("ordinal_booking", None, "Show me Bentleys")
    ask = a.chat("ordinal_booking", first["session_id"], "I want a booking")
    assert ask["booking"]["status"] == "needs_car"
    chosen = a.chat("ordinal_booking", first["session_id"], "3rd one")
    assert chosen["intent"] == "booking"
    assert chosen["booking"]["status"] == "needs_datetime"
    assert chosen["booking"]["listing_id"] == 100


def test_explicit_ambiguous_car_booking_uses_focused_matching_listing(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "focused_booking.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    first = a.chat("focused_booking", None, "Show me the 2024 Mercedes GLS")
    assert first["memory"]["short_term"]["focused_listing_id"] == 40
    ask = a.chat("focused_booking", first["session_id"], "Book the Mercedes GLS on Sunday at 10 AM")
    assert ask["intent"] == "booking"
    assert ask["booking"]["status"] == "invalid_day"
    assert ask["booking"]["listing_id"] == 40


def test_explicit_booking_time_validation_keeps_named_car(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "time_booking.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    first = a.chat("time_booking", None, "Show me the 2024 Mercedes GLS")
    answer = a.chat("time_booking", first["session_id"], "Book the Mercedes GLS Saturday at 7 AM")
    assert answer["intent"] == "booking"
    assert answer["booking"]["status"] == "invalid_time"
    assert answer["booking"]["listing_id"] == 40


def test_pending_booking_accepts_standalone_valid_datetime_reply(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "standalone_datetime.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    first = a.chat("standalone_datetime", None, "Show me the 2014 Ford Mustang")
    ask = a.chat("standalone_datetime", first["session_id"], "I want to book a viewing")
    assert ask["booking"]["status"] == "needs_datetime"
    assert ask["booking"]["listing_id"] == 20
    booked = a.chat("standalone_datetime", first["session_id"], "Saturday at 4 PM")
    assert booked["intent"] == "booking"
    assert booked["booking"]["status"] == "confirmed"
    assert booked["booking"]["listing_id"] == 20


def test_bare_booking_uses_single_exact_focused_result(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "single_focus_booking.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    first = a.chat("single_focus_booking", None, "Show me the 2024 Mercedes GLS")
    ask = a.chat("single_focus_booking", first["session_id"], "I want to book a viewing")
    assert ask["intent"] == "booking"
    assert ask["booking"]["status"] == "needs_datetime"
    assert ask["booking"]["listing_id"] == 40
    assert "2024 Mercedes-Benz Gls-Class" in ask["response"]


def test_bare_booking_still_asks_when_search_has_multiple_results(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "multi_focus_booking.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    first = a.chat("multi_focus_booking", None, "Show me BMWs")
    ask = a.chat("multi_focus_booking", first["session_id"], "I want to book a viewing")
    assert ask["intent"] == "booking"
    assert ask["booking"]["status"] == "needs_car"
    assert "Which car" in ask["response"]

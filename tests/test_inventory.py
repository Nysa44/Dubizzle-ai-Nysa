
from backend.inventory import Inventory


def test_inventory_loads_100_rows():
    inv = Inventory("data/cars_dataset.xlsx")
    assert len(inv.df) == 100


def test_make_filter_is_deterministic():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.schemas import CarFilter
    cars = inv.search(CarFilter(make="bentley"))
    assert len(cars) == 7
    assert all(c["make"] == "bentley" for c in cars)


def test_unknown_price_is_not_invented():
    inv = Inventory("data/cars_dataset.xlsx")
    row = inv.df.iloc[0]
    # A Ferrari listing may or may not have a cash price; this checks that
    # extraction does not fabricate a number from the model year.
    import pandas as pd
    assert pd.isna(row["price_aed"]) or row["price_aed"] >= 3000


def test_speed_is_not_mileage():
    inv = Inventory("data/cars_dataset.xlsx")
    car = inv.get(17)
    assert car["mileage_km"] is None
    assert car["top_speed_kmh"] == 318
    assert car["top_speed_mph"] == 198


def test_description_prices_are_extracted_without_monthly_finance():
    inv = Inventory("data/cars_dataset.xlsx")
    assert inv.get(3)["price_aed"] == 119750
    assert inv.get(15)["price_aed"] == 1349999
    assert inv.get(32)["price_aed"] == 70000
    assert inv.get(66)["price_aed"] == 79999
    assert inv.get(95)["price_aed"] == 95000


def test_mileage_prefers_odometer_over_service_mileage():
    inv = Inventory("data/cars_dataset.xlsx")
    assert inv.get(42)["mileage_km"] == 23900
    assert inv.get(47)["mileage_km"] == 122090


def test_vehicle_performance_facts_are_separated():
    inv = Inventory("data/cars_dataset.xlsx")
    ferrari = inv.get(38)
    assert ferrari["mileage_km"] is None
    assert ferrari["top_speed_kmh"] == 340
    assert ferrari["horsepower"] == 986
    assert ferrari["acceleration_0_100_s"] == 2.5


def test_description_price_and_monthly_are_separate():
    inv = Inventory("data/cars_dataset.xlsx")
    assert inv.get(60)["price_aed"] == 32000
    assert inv.get(15)["monthly_aed"] == 25683
    assert inv.get(32)["monthly_aed"] == 1750
    assert inv.get(40)["monthly_aed"] is None
    assert inv.get(92)["monthly_aed"] == 5805
    assert inv.get(92)["price_aed"] is None
    assert inv.get(97)["monthly_aed"] is None


def test_every_returned_car_contains_source_description_and_facts():
    inv = Inventory("data/cars_dataset.xlsx")
    for car in inv.search_text("warranty", limit=20):
        assert car["description"]
        assert "key_facts" in car


def test_mercedes_newest_returns_only_mercedes():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.schemas import CarFilter
    cars = inv.search(CarFilter(make="mercedes-benz", sort_by="newest"))
    assert len(cars) == 8
    assert all(c["make"] == "mercedes-benz" for c in cars)
    assert [c["year"] for c in cars[:4]] == [2024, 2024, 2023, 2022]


def test_showroom_8pm_is_not_monthly_payment():
    inv = Inventory("data/cars_dataset.xlsx")
    assert inv.get(40)["monthly_aed"] is None



def test_mileage_does_not_join_year_with_mileage():
    inv = Inventory("data/cars_dataset.xlsx")
    assert inv.get(65)["mileage_km"] == 71000
    assert inv.get(80)["mileage_km"] == 11000


def test_gcc_warranty_filter_uses_structured_fields():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.schemas import CarFilter
    q = CarFilter(keywords=[], requires_gcc=True, requires_warranty=True)
    assert inv.search_count(q) == 11
    cars = inv.search(q)
    assert len(cars) == 8
    assert all(c["regional_spec"] == "GCC" and c["warranty"] is True for c in cars)


def test_optional_warranty_boilerplate_is_not_treated_as_included():
    inv = Inventory("data/cars_dataset.xlsx")
    assert inv.get(46)["warranty"] is None
    assert inv.get(10)["warranty"] is None
    assert inv.get(73)["warranty"] is None



def test_gls_shorthand_resolves_to_canonical_model():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.parser import deterministic_parse
    q = deterministic_parse("Show me the 2024 Mercedes GLS", inv)
    assert q.make == "mercedes-benz"
    assert q.model == "gls-class"
    assert inv.search_count(q) == 1
    assert inv.search(q)[0]["listing_id"] == 40


def test_empty_search_returns_cleanly():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.parser import deterministic_parse
    q = deterministic_parse("Show me BMWs under AED 100k", inv)
    assert inv.search_count(q) == 0
    assert inv.search(q) == []


def test_all_mercedes_returns_all_twenty_when_requested():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.parser import deterministic_parse
    q = deterministic_parse("Show me all Mercedes", inv)
    q.limit = 20
    cars = inv.search(q)
    assert q.show_all is True
    assert len(cars) == 20
    assert all(c["make"] == "mercedes-benz" for c in cars)


def test_cheapest_and_most_expensive_are_direct_answers():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.agent import grounded_answer
    from backend.parser import deterministic_parse

    q = deterministic_parse("What is the cheapest car", inv)
    cars = inv.search(q)
    assert q.sort_by == "lowest_price"
    assert cars[0]["listing_id"] == 20
    answer = grounded_answer("What is the cheapest car", cars, q, {}, inv.search_count(q))
    assert "2014 Ford Mustang" in answer and "AED 21,500" in answer

    q = deterministic_parse("What is the most expensive car under AED 50k?", inv)
    cars = inv.search(q)
    assert q.sort_by == "highest_price"
    assert cars[0]["listing_id"] == 61
    answer = grounded_answer("What is the most expensive car under AED 50k?", cars, q, {}, inv.search_count(q))
    assert "2018 Toyota Camry" in answer and "AED 36,999" in answer


def test_inventory_wide_attribute_queries_are_not_generic_inventory_searches():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.parser import deterministic_parse

    cases = [
        ("Which cars have 7 seats?", {40, 54, 64}),
        ("Which cars mention panoramic roof?", {5, 6, 14, 19, 40, 59, 63, 64, 72, 87, 99}),
        ("Which cars mention accident free?", {4, 11, 12, 18, 19, 21, 25, 34, 39, 41, 56, 63, 72, 79, 89, 99}),
        ("Show me cars with a turbo engine", {17, 19, 38, 40, 54, 57, 71, 96}),
    ]
    for text, expected in cases:
        q = deterministic_parse(text, inv)
        ids = set(inv.search_ids(q))
        assert ids == expected


def test_exact_greeting_is_not_inventory_search():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.parser import deterministic_parse
    assert deterministic_parse("hi", inv).intent == "general_chat"
    assert deterministic_parse("thanks", inv).intent == "general_chat"
    assert deterministic_parse("okay", inv).intent == "general_chat"


def test_missing_exterior_colour_is_not_filled_from_unrelated_description_text():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.agent import grounded_answer
    from backend.parser import deterministic_parse
    q = deterministic_parse("What's the exterior colour?", inv)
    car = inv.get(12)
    answer = grounded_answer("What's the exterior colour?", [car], q, {}, 1)
    assert "Exterior colour" in answer
    assert "Not stated in the listing" in answer
    assert "Bank Auto finance" not in answer


def test_guardrails_cover_common_non_automotive_and_competitor_requests():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.parser import deterministic_parse
    for text in ["Who was Napoleon?", "Solve this math problem", "Write Python code", "What about Cars24?"]:
        assert deterministic_parse(text, inv).intent == "unknown"


def test_name_prompt_is_remembered_without_triggering_inventory_search():
    inv = Inventory("data/cars_dataset.xlsx")
    from backend.parser import deterministic_parse
    assert deterministic_parse("My name is Alex", inv).intent == "general_chat"


def test_long_term_memory_survives_a_new_session(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent

    monkeypatch.setattr(settings, "database_path", str(tmp_path / "memory.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()

    first = a.chat("memory_regression", None, "My name is Alex")
    assert first["intent"] == "general_chat"
    assert "Alex" in first["response"]

    a.chat("memory_regression", first["session_id"], "Show me SUVs under AED 50k")
    fresh = a.chat("memory_regression", None, "hi")
    assert fresh["memory"]["long_term"]["name"] == "Alex"
    assert fresh["memory"]["long_term"]["budget"]["max"] == 50000.0
    assert "Welcome back Alex" in fresh["response"]


def test_chat_and_guardrail_never_return_inventory_cards():
    from backend import db
    from backend.agent import Agent
    from backend.config import settings
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        settings.database_path = str(Path(d) / "chat.db")
        settings.leads_csv_path = str(Path(d) / "leads.csv")
        db.init_db()
        a = Agent()
        for text in ["hi", "hello", "thanks", "okay", "Who was Napoleon?", "Explain World War 2", "What is 2+2"]:
            result = a.chat("chat_guard_test", None, text)
            assert result["matched_cars"] == []
            assert result["total_matches"] == 0


def test_short_term_context_and_booking_require_an_explicit_car(tmp_path, monkeypatch):
    from backend.config import settings
    from backend import db
    from backend.agent import Agent
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "short.db"))
    monkeypatch.setattr(settings, "leads_csv_path", str(tmp_path / "leads.csv"))
    db.init_db()
    a = Agent()
    fresh = a.chat("short_term_user", None, "I want to book a viewing")
    assert fresh["booking"]["status"] == "needs_car"
    search = a.chat("short_term_user", fresh["session_id"], "Show me BMWs")
    assert search["memory"]["short_term"]["active_listing_ids"][:3] == [56, 19, 25]
    follow = a.chat("short_term_user", search["session_id"], "What's the mileage of the first one?")
    assert "27,000 km" in follow["response"]

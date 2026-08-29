
from backend.inventory import Inventory
from backend.parser import deterministic_parse


def test_budget_parser():
    inv = Inventory("data/cars_dataset.xlsx")
    q = deterministic_parse("Show me cars under AED 50k", inv)
    assert q.max_price_aed == 50000


def test_make_parser():
    inv = Inventory("data/cars_dataset.xlsx")
    q = deterministic_parse("Show me Bentleys with warranty", inv)
    assert q.make == "bentley"
    assert "warranty" in q.keywords


def test_mercedes_alias_and_newest_sort():
    inv = Inventory("data/cars_dataset.xlsx")
    q = deterministic_parse("Show me the newest Mercedes", inv)
    assert q.make == "mercedes-benz"
    assert q.sort_by == "newest"


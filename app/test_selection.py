"""Quick tests for selection logic — run: python -m app.test_selection"""
import datetime as dt
import random

from .selection import (
    _nth_weekday, _last_weekday, _easter, upcoming_special_day,
    choose_product, match_products,
)

PRODUCTS = [
    {"title": "Dad Is My Hero Keychain", "handle": "dad-keychain", "type": "Gift",
     "tags": ["dad", "father", "keychain"], "description": "A gift for dad, father's day.", "url": "u1"},
    {"title": "Luxury Sunglasses for Men", "handle": "sunglasses", "type": "Eyewear",
     "tags": ["men", "summer", "beach"], "description": "UV protection for outdoor beach days.", "url": "u2"},
    {"title": "Dog Mom Tumbler", "handle": "dog-tumbler", "type": "Drinkware",
     "tags": ["pet", "dog", "mom", "mother"], "description": "For the best dog mom. Mother's day gift.", "url": "u3"},
    {"title": "Cozy Winter Blanket", "handle": "blanket", "type": "Home",
     "tags": ["warm", "blanket", "cozy"], "description": "Indoor comfort and warmth.", "url": "u4"},
    {"title": "Baby Onesie", "handle": "onesie", "type": "Baby",
     "tags": ["baby", "infant", "newborn"], "description": "Soft newborn nursery wear.", "url": "u5"},
]


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}: {name}")
    assert cond, name


def main():
    # Floating holiday math — known 2026 dates
    check("Mother's Day 2026 = May 10", _nth_weekday(2026, 5, 6, 2) == dt.date(2026, 5, 10))
    check("Father's Day 2026 = Jun 21", _nth_weekday(2026, 6, 6, 3) == dt.date(2026, 6, 21))
    check("Memorial Day 2026 = May 25", _last_weekday(2026, 5, 0) == dt.date(2026, 5, 25))
    check("Thanksgiving 2026 = Nov 26", _nth_weekday(2026, 11, 3, 4) == dt.date(2026, 11, 26))
    check("Easter 2026 = Apr 5", _easter(2026) == dt.date(2026, 4, 5))

    # Ladder picks the SOONEST special day: mid-June -> Juneteenth (19th) before Father's (21st)
    day = upcoming_special_day(dt.date(2026, 6, 15))
    check("Soonest day mid-June is Juneteenth", day is not None and "Juneteenth" in day[0])

    # Father's Day is the nearest special day around June 19-21 once Juneteenth passes
    day_f = upcoming_special_day(dt.date(2026, 6, 20))
    check("Father's Day detected Jun 20", day_f is not None and "Father" in day_f[0])
    sel = choose_product(PRODUCTS, set(), today=dt.date(2026, 6, 20), rng=random.Random(1))
    check("Tier 1 selects dad product near Father's Day", sel.tier == 1 and sel.product["handle"] == "dad-keychain")

    # Repeat avoidance: if dad product was recent, it must not be re-selected
    sel2 = choose_product(PRODUCTS, {"dad-keychain"}, today=dt.date(2026, 6, 20), rng=random.Random(1))
    check("Repeat avoidance skips recent dad product", sel2.product["handle"] != "dad-keychain")

    # No holiday nearby -> falls to month/season; deep winter picks cozy/warm
    midwinter = dt.date(2026, 1, 20)
    sel3 = choose_product(PRODUCTS, set(), today=midwinter, rng=random.Random(2))
    check("Winter selection returns a product", sel3.product is not None)
    check("Winter tier is 2/3/4", sel3.tier in (2, 3, 4))

    # match_products scoring
    matched = match_products(PRODUCTS, ["dog", "pet"])
    check("Pet themes match the tumbler", matched and matched[0]["handle"] == "dog-tumbler")

    print("\nAll selection tests passed.")


if __name__ == "__main__":
    main()

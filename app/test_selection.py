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

    # Commemorative observances (Juneteenth) are excluded from product selection,
    # so mid-June the next product-appropriate day is Father's Day, not Juneteenth.
    day = upcoming_special_day(dt.date(2026, 6, 15))
    check("Mid-June skips Juneteenth (commemorative), finds Father's Day",
          day is not None and "Father" in day[0])

    # Father's Day is the nearest selectable day around June 19-21
    day_f = upcoming_special_day(dt.date(2026, 6, 20))
    check("Father's Day detected Jun 20", day_f is not None and "Father" in day_f[0])
    sel = choose_product(PRODUCTS, set(), today=dt.date(2026, 6, 20), rng=random.Random(1))
    check("Tier 1 selects dad product near Father's Day", sel.tier == 1 and sel.product["handle"] == "dad-keychain")

    # Repeat avoidance: if dad product was recent, it must not be re-selected
    sel2 = choose_product(PRODUCTS, {"dad-keychain"}, today=dt.date(2026, 6, 20), rng=random.Random(1))
    check("Repeat avoidance skips recent dad product", sel2.product["handle"] != "dad-keychain")

    # Commemorative exclusion: Juneteenth never appears in approaching days
    from .selection import approaching_special_days, COMMEMORATIVE_OBSERVANCES
    labels = [l for _, l, _ in approaching_special_days(dt.date(2026, 6, 1))]
    check("Juneteenth excluded from approaching days", "Juneteenth" not in labels)
    check("Veterans Day is in commemorative set", "Veterans Day" in COMMEMORATIVE_OBSERVANCES)

    # No holiday nearby -> falls to month/season; deep winter picks cozy/warm
    midwinter = dt.date(2026, 1, 20)
    sel3 = choose_product(PRODUCTS, set(), today=midwinter, rng=random.Random(2))
    check("Winter selection returns a product", sel3.product is not None)
    check("Winter tier is 2/3/4", sel3.tier in (2, 3, 4))

    # match_products scoring
    matched = match_products(PRODUCTS, ["dog", "pet"])
    check("Pet themes match the tumbler", matched and matched[0]["handle"] == "dog-tumbler")

    # NEW: strongly-themed holiday product is claimed by the approaching-holiday tier,
    # not absorbed into a weakly-matched month. June 5 -> Father's Day ~16 days out
    # (approaching, not imminent). The dad keychain strongly matches Father's Day.
    june5 = dt.date(2026, 6, 5)
    sel_dad = choose_product(PRODUCTS, set(), today=june5, rng=random.Random(3))
    check("June 5: dad product claimed for approaching Father's Day (tier 1)",
          sel_dad.tier == 1 and sel_dad.product["handle"] == "dad-keychain"
          and "Father" in sel_dad.reason)

    # NEW: with the dad product recently posted, June 5 should fall through to a
    # month/season pick that is NOT the reserved dad product.
    sel_other = choose_product(PRODUCTS, {"dad-keychain"}, today=june5, rng=random.Random(3))
    check("June 5: with dad posted, falls to non-dad product",
          sel_other.product["handle"] != "dad-keychain")

    # NEW: strong_holiday_affinity detects the dad keychain near Father's Day
    from .selection import strong_holiday_affinity
    aff = strong_holiday_affinity(PRODUCTS[0], june5)
    check("Affinity: dad keychain -> Father's Day", aff is not None and "Father" in aff)
    # and does NOT flag the unrelated blanket
    aff2 = strong_holiday_affinity(PRODUCTS[3], june5)
    check("Affinity: blanket has no approaching-holiday affinity", aff2 is None)

    print("\nAll selection tests passed.")


if __name__ == "__main__":
    main()

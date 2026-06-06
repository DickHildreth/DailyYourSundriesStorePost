"""Product selection logic for the daily Sundries post.

Walks the priority ladder and returns a chosen product plus the tier/reason:
  1. Upcoming special day (within LOOKAHEAD_DAYS)
  2. Current/upcoming special month
  3. Seasonal fit
  4. Random evergreen category

Pure functions where possible so this is unit-testable without network.
"""
from __future__ import annotations

import datetime as dt
import random
import re
from dataclasses import dataclass

LOOKAHEAD_DAYS = 10        # "imminent" — a holiday this close leads the post
APPROACHING_DAYS = 30      # "approaching" — strongly-themed products are reserved for it
STRONG_MATCH_MIN = 2       # >= this many theme-keyword hits == a strong thematic signal


# ---------------------------------------------------------------------------
# Floating-holiday date math (Northern Hemisphere, US-centric observances)
# ---------------------------------------------------------------------------
def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """nth occurrence of weekday (Mon=0) in month. n=1 -> first."""
    d = dt.date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + dt.timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    if month == 12:
        nxt = dt.date(year + 1, 1, 1)
    else:
        nxt = dt.date(year, month + 1, 1)
    last = nxt - dt.timedelta(days=1)
    offset = (last.weekday() - weekday) % 7
    return last - dt.timedelta(days=offset)


def _easter(year: int) -> dt.date:
    """Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return dt.date(year, month, day)


def special_days_for_year(year: int) -> list[tuple[dt.date, str, list[str]]]:
    """(date, occasion label, theme keywords)."""
    easter = _easter(year)
    days = [
        (dt.date(year, 1, 1), "New Year's Day", ["celebration", "organizer", "journal", "home"]),
        (dt.date(year, 2, 14), "Valentine's Day", ["gift", "romance", "jewelry", "candle", "heart", "couple"]),
        (easter - dt.timedelta(days=47), "Mardi Gras", ["party", "festive", "mask"]),
        (dt.date(year, 3, 17), "St. Patrick's Day", ["green", "festive", "party", "kitchen"]),
        (easter, "Easter", ["spring", "kids", "basket", "pastel", "candy"]),
        (dt.date(year, 5, 5), "Cinco de Mayo", ["party", "kitchen", "outdoor"]),
        (_nth_weekday(year, 5, 6, 2), "Mother's Day", ["mom", "mother", "gift for her", "jewelry", "self-care", "flower"]),
        (_last_weekday(year, 5, 0), "Memorial Day", ["patriotic", "outdoor", "bbq", "summer"]),
        (dt.date(year, 6, 19), "Juneteenth", ["celebration", "gift"]),
        (_nth_weekday(year, 6, 6, 3), "Father's Day", ["dad", "father", "gift for him", "tool", "grooming", "gadget", "watch"]),
        (dt.date(year, 7, 4), "Independence Day", ["patriotic", "outdoor", "bbq", "picnic", "red white blue"]),
        (_nth_weekday(year, 9, 0, 1), "Labor Day", ["outdoor", "home", "end of summer"]),
        (dt.date(year, 10, 31), "Halloween", ["costume", "decor", "kids", "spooky", "candy"]),
        (dt.date(year, 11, 11), "Veterans Day", ["patriotic", "gift"]),
        (_nth_weekday(year, 11, 3, 4), "Thanksgiving", ["kitchen", "table", "family", "fall", "gratitude"]),
        (dt.date(year, 12, 25), "Christmas", ["gift", "decor", "stocking", "family", "cozy", "holiday"]),
        (dt.date(year, 12, 31), "New Year's Eve", ["party", "celebration"]),
    ]
    # Black Friday / Cyber Monday relative to Thanksgiving
    tg = _nth_weekday(year, 11, 3, 4)
    days.append((tg + dt.timedelta(days=1), "Black Friday", ["deal", "gift", "bestseller"]))
    days.append((tg + dt.timedelta(days=4), "Cyber Monday", ["deal", "gift", "tech", "bestseller"]))
    return days


def upcoming_special_day(today: dt.date) -> tuple[str, list[str]] | None:
    """The soonest special day within LOOKAHEAD_DAYS, else None."""
    candidates = special_days_for_year(today.year) + special_days_for_year(today.year + 1)
    best = None
    for date, label, themes in candidates:
        delta = (date - today).days
        if 0 <= delta <= LOOKAHEAD_DAYS:
            if best is None or delta < best[0]:
                best = (delta, label, themes)
    if best:
        return best[1], best[2]
    return None


def approaching_special_days(today: dt.date,
                             horizon: int = APPROACHING_DAYS
                             ) -> list[tuple[int, str, list[str]]]:
    """All special days within `horizon` days, soonest first.

    Used to reserve strongly-themed products for an approaching holiday so they
    aren't absorbed into a weakly-matched month/season tier.
    """
    candidates = special_days_for_year(today.year) + special_days_for_year(today.year + 1)
    out = []
    for date, label, themes in candidates:
        delta = (date - today).days
        if 0 <= delta <= horizon:
            out.append((delta, label, themes))
    out.sort(key=lambda x: x[0])
    return out


# ---------------------------------------------------------------------------
# Special months
# ---------------------------------------------------------------------------
SPECIAL_MONTHS = {
    1: ("New Year wellness", ["fitness", "organization", "journal"]),
    2: ("Black History Month / American Heart Month", ["celebration", "wellness", "red"]),
    3: ("Women's History Month", ["gift for her", "empowerment", "jewelry"]),
    4: ("Earth Month", ["eco", "reusable", "plant", "outdoor"]),
    5: ("Mental Health Awareness", ["self-care", "wellness", "calm"]),
    6: ("Pride Month", ["colorful", "celebration", "gift"]),
    7: ("Summer", ["outdoor", "beach", "travel"]),
    8: ("Back-to-School", ["kids", "organization", "supplies"]),
    9: ("Back-to-School / Fall start", ["home", "cozy", "kids"]),
    10: ("Breast Cancer Awareness", ["pink", "wellness"]),
    11: ("Gratitude", ["family", "kitchen", "gift"]),
    12: ("Holidays", ["gift", "decor", "cozy"]),
}


def month_theme(today: dt.date) -> tuple[str, list[str]]:
    return SPECIAL_MONTHS[today.month]


# ---------------------------------------------------------------------------
# Seasons (Northern Hemisphere)
# ---------------------------------------------------------------------------
def season_theme(today: dt.date) -> tuple[str, list[str]]:
    m = today.month
    if m in (3, 4, 5):
        return "Spring", ["garden", "outdoor", "cleaning", "pastel", "fresh"]
    if m in (6, 7, 8):
        return "Summer", ["beach", "cooling", "travel", "hydration", "outdoor"]
    if m in (9, 10, 11):
        return "Fall", ["cozy", "home", "warm", "decor", "layer"]
    return "Winter", ["warm", "blanket", "comfort", "indoor", "gift"]


# ---------------------------------------------------------------------------
# Evergreen random categories
# ---------------------------------------------------------------------------
EVERGREEN = {
    "pets": ["pet", "dog", "cat", "paw"],
    "babies": ["baby", "infant", "newborn", "nursery"],
    "children": ["kid", "child", "toy", "children"],
    "birthdays": ["birthday", "gift", "celebration"],
    "home": ["home", "decor", "house"],
    "kitchen": ["kitchen", "cook", "mug", "tumbler", "drink"],
    "gifts": ["gift", "present", "keepsake"],
    "self-care": ["self-care", "spa", "relax", "wellness"],
    "gadgets": ["gadget", "tech", "device"],
}


def random_evergreen(rng: random.Random) -> tuple[str, list[str]]:
    cat = rng.choice(list(EVERGREEN.keys()))
    return cat, EVERGREEN[cat]


# ---------------------------------------------------------------------------
# Matching products to themes
# ---------------------------------------------------------------------------
def _haystack(product: dict) -> str:
    parts = [
        product.get("title", ""),
        product.get("type", ""),
        " ".join(product.get("tags") or []),
        product.get("description", ""),
    ]
    return " ".join(parts).lower()


def match_products(products: list[dict], themes: list[str]) -> list[dict]:
    """Products whose text matches any theme keyword, scored by match count."""
    return [p for p, _ in match_products_scored(products, themes)]


def match_products_scored(products: list[dict],
                          themes: list[str]) -> list[tuple[dict, int]]:
    """(product, score) for products matching any theme keyword, best first."""
    scored = []
    for p in products:
        hay = _haystack(p)
        score = sum(1 for kw in themes if kw.lower() in hay)
        if score > 0:
            scored.append((p, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def theme_score(product: dict, themes: list[str]) -> int:
    hay = _haystack(product)
    return sum(1 for kw in themes if kw.lower() in hay)


def strong_holiday_affinity(product: dict, today: dt.date) -> str | None:
    """If the product STRONGLY matches an approaching holiday, return that holiday's
    label; else None. Used to keep e.g. a Father's Day keychain from being posted
    under a loosely-matched Pride Month theme when Father's Day is still weeks out.
    """
    for _delta, label, themes in approaching_special_days(today):
        if theme_score(product, themes) >= STRONG_MATCH_MIN:
            return label
    return None


@dataclass
class Selection:
    product: dict
    tier: int
    reason: str
    themes: list[str]


def choose_product(products: list[dict], recent_handles: set[str],
                   today: dt.date | None = None,
                   rng: random.Random | None = None) -> Selection:
    """Walk the priority ladder, skipping products posted recently."""
    today = today or dt.date.today()
    rng = rng or random.Random()

    def first_fresh(matched: list[dict],
                    reserve_check: bool = False) -> dict | None:
        """First fresh product. If reserve_check, skip products that strongly
        belong to an approaching holiday (they're reserved for the holiday tier)."""
        for p in matched:
            if p.get("handle") in recent_handles:
                continue
            if reserve_check and strong_holiday_affinity(p, today):
                continue
            return p
        return None

    # Tier 1a — imminent special day (within LOOKAHEAD_DAYS): leads the post.
    day = upcoming_special_day(today)
    if day:
        label, themes = day
        pick = first_fresh(match_products(products, themes))
        if pick:
            return Selection(pick, 1, f"Upcoming special day: {label}", themes)

    # Tier 1b — approaching holiday (within APPROACHING_DAYS) for which a product is
    # a STRONG thematic match. This claims e.g. a Father's Day keychain for Father's
    # Day even before the imminent window, instead of letting a weak keyword pull it
    # into the current month tier.
    for _delta, label, themes in approaching_special_days(today):
        scored = match_products_scored(products, themes)
        strong = [p for p, s in scored
                  if s >= STRONG_MATCH_MIN and p.get("handle") not in recent_handles]
        if strong:
            return Selection(strong[0], 1, f"Approaching special day: {label}", themes)

    # Tier 2 — special month (skipping products reserved for an approaching holiday)
    mlabel, mthemes = month_theme(today)
    pick = first_fresh(match_products(products, mthemes), reserve_check=True)
    if pick:
        return Selection(pick, 2, f"Special month: {mlabel}", mthemes)

    # Tier 3 — season (also reserving approaching-holiday products)
    slabel, sthemes = season_theme(today)
    pick = first_fresh(match_products(products, sthemes), reserve_check=True)
    if pick:
        return Selection(pick, 3, f"Seasonal fit: {slabel}", sthemes)

    # Tier 4 — random evergreen; try a few categories before giving up
    for _ in range(len(EVERGREEN)):
        cat, themes = random_evergreen(rng)
        pick = first_fresh(match_products(products, themes), reserve_check=True)
        if pick:
            return Selection(pick, 4, f"Random evergreen: {cat}", themes)

    # Absolute fallback: any fresh product at random
    fresh = [p for p in products if p.get("handle") not in recent_handles]
    pool = fresh or products
    pick = rng.choice(pool)
    return Selection(pick, 4, "Fallback: random product", [])

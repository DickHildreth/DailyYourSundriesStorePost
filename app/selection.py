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
# With weighted scoring (title/tags = 3 each, type = 2, desc = 1), a STRONG signal
# means at least a title/tag-level hit plus a bit more — not just generic description
# keywords. 4 requires e.g. a tag hit (3) + a description echo (1), or two field hits.
STRONG_MATCH_MIN = 4


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


# Commemorative / solemn observances that should NOT be used as a hook to sell a
# product. Grafting a commercial post onto these reads as opportunistic and can
# draw backlash, so they're excluded from the product-occasion tiers. (They can
# still be handled by a separate, non-commercial posting flow if ever desired.)
COMMEMORATIVE_OBSERVANCES = {
    "Juneteenth",
    "Veterans Day",
    "Memorial Day",
}


def _product_special_days(year: int):
    """special_days_for_year minus commemorative observances."""
    return [(d, label, themes) for (d, label, themes) in special_days_for_year(year)
            if label not in COMMEMORATIVE_OBSERVANCES]


def upcoming_special_day(today: dt.date) -> tuple[str, list[str]] | None:
    """The soonest product-appropriate special day within LOOKAHEAD_DAYS, else None."""
    candidates = _product_special_days(today.year) + _product_special_days(today.year + 1)
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
    candidates = _product_special_days(today.year) + _product_special_days(today.year + 1)
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


# Field weights: a product IS what its title/tags say; the description is marketing
# prose where generic keywords ("gift", "him", "tool") accumulate incidentally.
WEIGHT_TITLE = 3
WEIGHT_TAGS = 3
WEIGHT_TYPE = 2
WEIGHT_DESC = 1


def weighted_theme_score(product: dict, themes: list[str]) -> int:
    """Score theme matches, weighting title/tags far above the description.

    A keyword in the title or tags counts much more than the same word buried in a
    long description, so 'Dad Is My Hero Keychain' (dad in title+tags) outranks a
    'Diamond Hardness Tester' that only mentions 'gift for him' in its blurb.
    """
    title = (product.get("title") or "").lower()
    tags = " ".join(product.get("tags") or []).lower()
    ptype = (product.get("type") or "").lower()
    desc = (product.get("description") or "").lower()
    score = 0
    for kw in themes:
        k = kw.lower()
        if k in title:
            score += WEIGHT_TITLE
        if k in tags:
            score += WEIGHT_TAGS
        if k in ptype:
            score += WEIGHT_TYPE
        if k in desc:
            score += WEIGHT_DESC
    return score


def match_products(products: list[dict], themes: list[str]) -> list[dict]:
    """Products whose text matches any theme keyword, best (weighted) first."""
    return [p for p, _ in match_products_scored(products, themes)]


def match_products_scored(products: list[dict],
                          themes: list[str]) -> list[tuple[dict, int]]:
    """(product, weighted_score) for matching products, best first."""
    scored = []
    for p in products:
        score = weighted_theme_score(p, themes)
        if score > 0:
            scored.append((p, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def theme_score(product: dict, themes: list[str]) -> int:
    return weighted_theme_score(product, themes)


def strong_holiday_affinity(product: dict, today: dt.date) -> str | None:
    """If the product STRONGLY matches an approaching holiday, return that holiday's
    label; else None. Used to keep e.g. a Father's Day keychain from being posted
    under a loosely-matched Pride Month theme when Father's Day is still weeks out.
    """
    for _delta, label, themes in approaching_special_days(today):
        if weighted_theme_score(product, themes) >= STRONG_MATCH_MIN:
            return label
    return None


@dataclass
class Selection:
    product: dict
    tier: int
    reason: str
    themes: list[str]
    shortlist: list[dict] | None = None  # ranked candidates for this tier (for Claude chooser)
    is_occasion: bool = False            # True for holiday/month tiers that need a genuine fit
                                         # even with one candidate; False for broad fallbacks


SHORTLIST_SIZE = 6


def candidate_tiers(products: list[dict], recent_handles: set[str],
                    today: dt.date | None = None,
                    rng: random.Random | None = None) -> list[Selection]:
    """Ordered list of viable tiers, each a Selection with a ranked `shortlist`.

    The orchestrator walks these in order, asking Claude to pick a genuine fit from
    each tier's shortlist; if Claude judges a tier has no good fit, it advances to the
    next tier. Commemorative observances are already excluded from the holiday tiers.
    The final season/evergreen tiers are broad, so the chain reliably terminates in a
    genuine fit rather than ever forcing a mismatched occasion post.
    """
    today = today or dt.date.today()
    rng = rng or random.Random()
    tiers: list[Selection] = []

    def fresh_only(prods: list[dict], reserve_check: bool = False) -> list[dict]:
        out = []
        for p in prods:
            if p.get("handle") in recent_handles:
                continue
            if reserve_check and strong_holiday_affinity(p, today):
                continue
            out.append(p)
        return out

    # Tier 1a — imminent special day
    day = upcoming_special_day(today)
    if day:
        label, themes = day
        cands = fresh_only(match_products(products, themes))
        if cands:
            tiers.append(Selection(cands[0], 1, f"Upcoming special day: {label}",
                                   themes, shortlist=cands[:SHORTLIST_SIZE],
                                   is_occasion=True))

    # Tier 1b — approaching holiday with a STRONG product match
    for _delta, label, themes in approaching_special_days(today):
        scored = match_products_scored(products, themes)
        strong = [p for p, s in scored
                  if s >= STRONG_MATCH_MIN and p.get("handle") not in recent_handles]
        if strong:
            tiers.append(Selection(strong[0], 1, f"Approaching special day: {label}",
                                   themes, shortlist=strong[:SHORTLIST_SIZE],
                                   is_occasion=True))
            break  # only the soonest approaching holiday

    # Tier 2 — special month
    mlabel, mthemes = month_theme(today)
    mcands = fresh_only(match_products(products, mthemes), reserve_check=True)
    if mcands:
        tiers.append(Selection(mcands[0], 2, f"Special month: {mlabel}", mthemes,
                               shortlist=mcands[:SHORTLIST_SIZE], is_occasion=True))

    # Tier 3 — season (broad; a genuine fit is easy, auto-accept allowed)
    slabel, sthemes = season_theme(today)
    scands = fresh_only(match_products(products, sthemes), reserve_check=True)
    if scands:
        tiers.append(Selection(scands[0], 3, f"Seasonal fit: {slabel}", sthemes,
                               shortlist=scands[:SHORTLIST_SIZE], is_occasion=False))

    # Tier 4 — random evergreen (broad category)
    for _ in range(len(EVERGREEN)):
        cat, themes = random_evergreen(rng)
        ecands = fresh_only(match_products(products, themes), reserve_check=True)
        if ecands:
            tiers.append(Selection(ecands[0], 4, f"Random evergreen: {cat}", themes,
                                   shortlist=ecands[:SHORTLIST_SIZE], is_occasion=False))
            break

    # Absolute fallback — any fresh product
    fresh = [p for p in products if p.get("handle") not in recent_handles]
    pool = fresh or products
    if pool:
        sample = rng.sample(pool, min(SHORTLIST_SIZE, len(pool)))
        tiers.append(Selection(sample[0], 4, "General catalog pick", [],
                               shortlist=sample, is_occasion=False))
    return tiers


def choose_product(products: list[dict], recent_handles: set[str],
                   today: dt.date | None = None,
                   rng: random.Random | None = None) -> Selection:
    """Convenience: the top viable tier (keyword-ranked, no Claude judgment).

    Kept for tests and simple callers. The orchestrator uses candidate_tiers() so it
    can cascade past tiers Claude judges to have no genuine fit.
    """
    tiers = candidate_tiers(products, recent_handles, today, rng)
    return tiers[0]

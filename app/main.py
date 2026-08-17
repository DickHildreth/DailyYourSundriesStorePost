"""Daily Sundries autopost orchestrator.

Pipeline: fetch catalog -> select product -> write copy (Anthropic API)
-> publish (Facebook) -> log. Fails loudly; never posts partial/garbage.

Run:
  python -m app.main            # full run: select, write, publish, log
  python -m app.main --dry-run  # everything except publish + log
"""
from __future__ import annotations

import argparse
import datetime as dt
import random
import sys

from . import catalog, copywriter, postlog, publisher
from .selection import candidate_tiers as choose_tiers
from .verify_setup import verify_all

MAX_JITTER_MINUTES = 90


def log(msg: str) -> None:
    print(f"[{dt.datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def should_post_today(today: dt.date | None = None, salt: str = "sundries-posting") -> bool:
    """Deterministic 4–5 posting days per ISO week.

    We hash the ISO week start plus a stored salt to generate a per-week RNG. That keeps
    the same date stable across reruns, while the pattern rotates each week so the skip days
    vary instead of always falling on the same weekdays.
    """
    today = today or dt.date.today()
    iso_year, iso_week, _ = today.isocalendar()
    week_start = dt.date.fromisocalendar(iso_year, iso_week, 1)
    rng = random.Random(f"{week_start.isoformat()}|{salt}")
    weekdays = list(range(7))
    post_days = set(rng.sample(weekdays, k=rng.choice([4, 5])))
    return today.weekday() in post_days


def apply_jitter(force: bool = False, dry_run: bool = False) -> None:
    if force or dry_run:
        log("Jitter: skipped (--dry-run or --force).")
        return
    minutes = random.randint(0, MAX_JITTER_MINUTES)
    log(f"Jitter: sleeping {minutes} minute(s) before publish.")
    import time
    time.sleep(minutes * 60)


def preflight() -> bool:
    log("Running pre-flight credential checks...")
    ok, lines = verify_all()
    for line in lines:
        log("  " + line)
    log("Pre-flight: " + ("PASSED" if ok else "FAILED"))
    return ok


def run(dry_run: bool = False, skip_preflight: bool = False, force: bool = False) -> int:
    if not force and not should_post_today():
        log("Skip day — not posting today")
        return 0

    if not skip_preflight:
        if not preflight():
            log("ERROR: pre-flight checks failed; not posting.")
            return 1

    apply_jitter(force=force, dry_run=dry_run)

    log("Fetching catalog...")
    products = catalog.fetch_catalog()
    log(f"Catalog: {len(products)} products.")

    recent = postlog.recent_handles()
    log(f"Recently posted (skip list): {len(recent)} handles.")

    tiers = choose_tiers(products, recent)
    log(f"{len(tiers)} candidate tier(s) to consider.")

    chosen = None
    occasion = None
    chosen_tier = None
    for tier in tiers:
        shortlist = tier.shortlist or [tier.product]
        log(f"Tier {tier.tier} — {tier.reason}: {len(shortlist)} candidate(s)"
            f"{' [occasion]' if tier.is_occasion else ''}.")
        # Broad (non-occasion) tier with a single candidate: accept without a fit-check.
        # Occasion tiers ALWAYS get a fit-check, even with one candidate, so a lone
        # weak holiday match can be rejected rather than forced into a mismatched post.
        if len(shortlist) == 1 and not tier.is_occasion:
            chosen, occasion, chosen_tier = shortlist[0], tier.reason, tier.tier
            log(f"  Single candidate (broad tier), accepting: '{chosen.get('title')}'")
            break
        idx, fits, why = copywriter.choose_best_product(tier.reason, shortlist)
        cand = shortlist[idx]
        log(f"  Claude: '{cand.get('title')}' fits={fits} — {why}")
        if fits:
            chosen, occasion, chosen_tier = cand, tier.reason, tier.tier
            break
        log("  No genuine fit for this occasion; advancing to next tier.")

    if chosen is None:
        log("ERROR: no tier produced a genuine fit; skipping today's post.")
        return 1

    log(f"Final selection: '{chosen.get('title')}' (tier {chosen_tier} — {occasion})")

    log("Generating copy via Anthropic API...")
    message = copywriter.write_post(chosen, occasion)
    log("Copy generated:\n" + "-" * 60 + f"\n{message}\n" + "-" * 60)

    if dry_run:
        log("DRY RUN — not publishing, not logging.")
        return 0

    log("Publishing to Facebook...")
    result = publisher.publish_link_post(message, chosen["url"])
    post_id = result.get("id") or result.get("post_id")
    log(f"Published. Post ID: {post_id}")

    postlog.append(
        chosen["handle"],
        chosen["title"],
        chosen_tier,
        product_type=chosen.get("type") or chosen.get("product_type"),
        theme=occasion,
    )
    log("Logged. Done.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="select + write but do not publish or log")
    ap.add_argument("--force", action="store_true",
                    help="bypass the skip-day check for manual runs/testing")
    ap.add_argument("--skip-preflight", action="store_true",
                    help="skip credential checks before running")
    ap.add_argument("--verify-only", action="store_true",
                    help="run only the credential checks, then exit")
    args = ap.parse_args()
    try:
        if args.verify_only:
            ok = preflight()
            return 0 if ok else 1
        return run(dry_run=args.dry_run, skip_preflight=args.skip_preflight, force=args.force)
    except Exception as e:  # fail loudly with non-zero exit for the scheduler
        log(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

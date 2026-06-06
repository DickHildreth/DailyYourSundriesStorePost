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
import sys

from . import catalog, copywriter, postlog, publisher
from .selection import choose_product
from .verify_setup import verify_all


def log(msg: str) -> None:
    print(f"[{dt.datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def preflight() -> bool:
    log("Running pre-flight credential checks...")
    ok, lines = verify_all()
    for line in lines:
        log("  " + line)
    log("Pre-flight: " + ("PASSED" if ok else "FAILED"))
    return ok


def run(dry_run: bool = False, skip_preflight: bool = False) -> int:
    if not skip_preflight:
        if not preflight():
            log("ERROR: pre-flight checks failed; not posting.")
            return 1

    log("Fetching catalog...")
    products = catalog.fetch_catalog()
    log(f"Catalog: {len(products)} products.")

    recent = postlog.recent_handles()
    log(f"Recently posted (skip list): {len(recent)} handles.")

    sel = choose_product(products, recent)
    log(f"Selected: '{sel.product.get('title')}' (tier {sel.tier} — {sel.reason})")

    log("Generating copy via Anthropic API...")
    message = copywriter.write_post(sel.product, sel.reason)
    log("Copy generated:\n" + "-" * 60 + f"\n{message}\n" + "-" * 60)

    if dry_run:
        log("DRY RUN — not publishing, not logging.")
        return 0

    log("Publishing to Facebook...")
    result = publisher.publish_link_post(message, sel.product["url"])
    post_id = result.get("id") or result.get("post_id")
    log(f"Published. Post ID: {post_id}")

    postlog.append(sel.product["handle"], sel.product["title"], sel.tier)
    log("Logged. Done.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="select + write but do not publish or log")
    ap.add_argument("--skip-preflight", action="store_true",
                    help="skip credential checks before running")
    ap.add_argument("--verify-only", action="store_true",
                    help="run only the credential checks, then exit")
    args = ap.parse_args()
    try:
        if args.verify_only:
            ok = preflight()
            return 0 if ok else 1
        return run(dry_run=args.dry_run, skip_preflight=args.skip_preflight)
    except Exception as e:  # fail loudly with non-zero exit for the scheduler
        log(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

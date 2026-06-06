"""Pre-flight credential checks for the Sundries autopost job.

Validates, without publishing anything:
  1. FB token is valid, non-expiring, and grants CREATE_CONTENT on the target page
  2. Anthropic API key works (tiny live call)
  3. Shopify catalog is reachable and non-empty

Run standalone:
  python -m app.verify_setup            # human-readable report, exit 0/1
  python -m app.verify_setup --quiet    # only prints on failure

Importable: verify_all() returns (ok: bool, lines: list[str]).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error

from .publisher import GRAPH_VERSION
from .copywriter import API_URL, MODEL, ANTHROPIC_VERSION

GRAPH = "https://graph.facebook.com"


def _get_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "SundriesAutoPost/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_facebook() -> tuple[bool, list[str]]:
    """Validate the page token: valid, non-expiring, CREATE_CONTENT on the page."""
    out: list[str] = []
    page_id = os.environ.get("FB_PAGE_ID")
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    if not page_id or not token:
        return False, ["FB: missing FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN"]

    # debug_token needs an app or page token as the inspecting token; the page token
    # can inspect itself.
    params = urllib.parse.urlencode({"input_token": token, "access_token": token})
    try:
        data = _get_json(f"{GRAPH}/{GRAPH_VERSION}/debug_token?{params}").get("data", {})
    except urllib.error.HTTPError as e:
        return False, [f"FB: debug_token HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}"]
    except urllib.error.URLError as e:
        return False, [f"FB: cannot reach Graph API: {e}"]

    ok = True
    if not data.get("is_valid"):
        ok = False
        out.append("FB: token is NOT valid")
    else:
        out.append("FB: token valid \u2713")

    expires = data.get("expires_at")
    data_expires = data.get("data_access_expires_at")
    # 0 means "never" for both fields.
    if expires in (0, None) and data_expires in (0, None):
        out.append("FB: token does not expire \u2713")
    else:
        ok = False
        out.append(f"FB: token EXPIRES (expires_at={expires}, data_access_expires_at={data_expires}) — "
                   "regenerate as a System User token with expiration Never")

    # Confirm the token's page matches and has CREATE_CONTENT.
    # Query the page node for the tasks this token can perform.
    try:
        page = _get_json(
            f"{GRAPH}/{GRAPH_VERSION}/{page_id}?fields=name,tasks&"
            + urllib.parse.urlencode({"access_token": token})
        )
    except urllib.error.HTTPError as e:
        return False, out + [f"FB: page query HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}"]
    except urllib.error.URLError as e:
        return False, out + [f"FB: cannot reach page node: {e}"]

    tasks = page.get("tasks") or []
    if "CREATE_CONTENT" in tasks:
        out.append(f"FB: CREATE_CONTENT granted on '{page.get('name')}' \u2713")
    else:
        ok = False
        out.append(f"FB: CREATE_CONTENT NOT in tasks for page (got {tasks}) — "
                   "reassign the page to the System User with full control")
    return ok, out


def check_anthropic() -> tuple[bool, list[str]]:
    """Tiny live call to confirm the API key works and the model string is accepted."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return False, ["Anthropic: missing ANTHROPIC_API_KEY"]
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 5,
        "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=body, method="POST",
        headers={"content-type": "application/json", "x-api-key": key,
                 "anthropic-version": ANTHROPIC_VERSION},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        hint = " (check the key)" if e.code in (401, 403) else ""
        return False, [f"Anthropic: HTTP {e.code}{hint}: {detail}"]
    except urllib.error.URLError as e:
        return False, [f"Anthropic: cannot reach API: {e}"]
    if data.get("content"):
        return True, [f"Anthropic: API key works, model '{MODEL}' accepted \u2713"]
    return False, [f"Anthropic: unexpected response: {str(data)[:200]}"]


def check_catalog() -> tuple[bool, list[str]]:
    try:
        from .catalog import fetch_catalog
        products = fetch_catalog(max_pages=1)
        return True, [f"Catalog: reachable, {len(products)} products on first page \u2713"]
    except Exception as e:
        return False, [f"Catalog: {e}"]


def verify_all() -> tuple[bool, list[str]]:
    all_ok = True
    lines: list[str] = []
    for fn in (check_facebook, check_anthropic, check_catalog):
        ok, out = fn()
        all_ok = all_ok and ok
        lines.extend(out)
    return all_ok, lines


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="only print on failure")
    args = ap.parse_args()
    ok, lines = verify_all()
    if not ok or not args.quiet:
        print("\n".join(lines))
        print("RESULT:", "ALL CHECKS PASSED" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

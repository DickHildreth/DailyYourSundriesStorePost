"""Fetch the yoursundries.store catalog via the Shopify products.json endpoint."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

BASE = "https://yoursundries.store"
MAX_ATTEMPTS = 4
BACKOFF_SECONDS = (2, 4, 8)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()


def _simplify(p: dict) -> dict:
    images = p.get("images") or []
    variants = p.get("variants") or []
    return {
        "title": p.get("title"),
        "handle": p.get("handle"),
        "url": f"{BASE}/products/{p.get('handle')}",
        "price": variants[0].get("price") if variants else None,
        "image": images[0].get("src") if images else None,
        "type": p.get("product_type"),
        "tags": p.get("tags") or [],
        "description": _strip_html(p.get("body_html"))[:600],
    }


def fetch_catalog(max_pages: int = 10) -> list[dict]:
    products: list[dict] = []
    for page in range(1, max_pages + 1):
        url = f"{BASE}/products.json?limit=250&page={page}"
        last_error: Exception | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                break
            except (urllib.error.HTTPError, urllib.error.URLError) as e:
                last_error = e
                status = getattr(e, "code", None)
                transient = status in (429, 500, 502, 503, 504) or isinstance(e, urllib.error.URLError)
                if transient and attempt < MAX_ATTEMPTS:
                    sleep_for = BACKOFF_SECONDS[attempt - 1]
                    time.sleep(sleep_for)
                    continue
                raise RuntimeError(
                    f"Could not reach Shopify catalog at {url} after {attempt} attempt(s): {e}. "
                    "Check the store URL and that egress to yoursundries.store is allowed."
                ) from e
            except json.JSONDecodeError as e:
                last_error = e
                if attempt < MAX_ATTEMPTS:
                    time.sleep(BACKOFF_SECONDS[attempt - 1])
                    continue
                raise RuntimeError(f"Invalid JSON from Shopify catalog at {url}: {e}") from e
        else:
            raise RuntimeError(f"Catalog fetch gave up after {MAX_ATTEMPTS} attempts for {url}: {last_error}")
        batch = data.get("products", [])
        if not batch:
            break
        products.extend(_simplify(p) for p in batch)
    if not products:
        raise RuntimeError("Catalog fetch returned zero products.")
    return products

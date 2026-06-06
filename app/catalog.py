"""Fetch the yoursundries.store catalog via the Shopify products.json endpoint."""
from __future__ import annotations

import re
import urllib.request
import urllib.error
import json

BASE = "https://yoursundries.store"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SundriesAutoPost/1.0)"}


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
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Could not reach Shopify catalog at {url}: {e}. "
                "Check the store URL and that egress to yoursundries.store is allowed."
            ) from e
        batch = data.get("products", [])
        if not batch:
            break
        products.extend(_simplify(p) for p in batch)
    if not products:
        raise RuntimeError("Catalog fetch returned zero products.")
    return products

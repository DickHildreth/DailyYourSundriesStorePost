"""Publish a link post to the Facebook page via the Graph API."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import urllib.error

GRAPH_VERSION = "v25.0"


def publish_link_post(message: str, link: str, *, page_id: str | None = None,
                      token: str | None = None) -> dict:
    page_id = page_id or os.environ.get("FB_PAGE_ID")
    token = token or os.environ.get("FB_PAGE_ACCESS_TOKEN")
    if not page_id or not token:
        raise RuntimeError(
            "Missing FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN environment variables."
        )

    endpoint = f"https://graph.facebook.com/{GRAPH_VERSION}/{page_id}/feed"
    data = urllib.parse.urlencode({
        "message": message,
        "link": link,
        "access_token": token,
    }).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        hint = ""
        if e.code in (190, 401, 403) or "OAuth" in detail:
            hint = (" This looks like a token problem. Regenerate the System User token "
                    "in Business Settings (it should not expire).")
        raise RuntimeError(f"Graph API error {e.code}: {detail}.{hint}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error reaching Graph API: {e}") from e

"""Generate the post copy by calling the Anthropic Messages API.

Uses only the stdlib (urllib) so the container needs no SDK dependency.
Model is pinned to a versioned string per Anthropic best practice.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"          # versioned, not an alias
ANTHROPIC_VERSION = "2023-06-01"

VOICE_SYSTEM_PROMPT = """You are the copywriter for the Facebook page "Your Sundries Store". \
Write ONE Facebook post promoting a single product, in the page's established voice.

The page's voice and exact structure (follow precisely):

1. Hook line: start with a themed emoji (or two), then a short, emotionally evocative \
sentence that usually trails into an ellipsis. Set a FEELING, not a sales pitch.
2. Emotional body: one or two short paragraphs building a scene/story, then introduce the \
product with this signature framing: "The [Product Name] is more than a [thing] - it's a \
[deeper emotional meaning]." Use a spaced hyphen " - ", never an em dash.
3. Three-fragment feature line: three short noun phrases, each ending in a period \
(e.g. "Bold design. Premium shine. Effortless presence.").
4. A line opened by the sparkles emoji then "Because ...", a reflective one-liner trailing \
into an ellipsis.
5. A line opened by the pointing-right emoji: an action verb (Elevate / Celebrate / Add / \
Gift / Remind) then "... [verb] the [Product Name] today." (may reference the occasion).
6. A line opened by the shopping-cart emoji followed by the exact product URL provided.
7. A hashtag block of 8-11 PascalCase hashtags tied to the product and occasion, closing \
with 1-3 emojis.

Tone: warm, sentimental, aspirational, lightly grandiose. Short sentences and fragments. \
Treat the product as a vessel for a feeling (love, legacy, confidence, identity). \
Paraphrase the product's real features into the emotional framing; do NOT invent specs not \
supported by the provided product details. Do NOT copy the product description verbatim.

Output ONLY the post text, ready to publish. No preamble, no explanation, no quotation marks \
around the whole thing."""


def _build_user_prompt(product: dict, occasion_reason: str) -> str:
    return f"""Write today's post for this product.

Occasion / why selected: {occasion_reason}

Product details (use only what's here for facts):
- Name: {product.get('title')}
- URL (use exactly on the cart line): {product.get('url')}
- Type: {product.get('type')}
- Tags: {', '.join(product.get('tags') or [])}
- Description: {product.get('description')}
"""


def write_post(product: dict, occasion_reason: str, *, api_key: str | None = None,
               max_tokens: int = 600) -> str:
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing ANTHROPIC_API_KEY. Set it as an environment variable "
            "(create/reuse a key at console.anthropic.com)."
        )

    body = json.dumps({
        "model": MODEL,
        "max_tokens": max_tokens,
        "system": VOICE_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": _build_user_prompt(product, occasion_reason)}
        ],
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL, data=body, method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"Anthropic API error {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error reaching Anthropic API: {e}") from e

    # Concatenate text blocks
    parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
    text = "".join(parts).strip()
    if not text:
        raise RuntimeError(f"Anthropic API returned no text. Full response: {data}")
    return text

---
name: daily-fb-product-post
description: Create and auto-publish one daily Facebook product post for the "Your Sundries Store" fan page, featuring a product from yoursundries.store with a "Shop Now" CTA. Use this whenever the user asks to make the daily post, the daily Facebook post, today's product post, the Sundries post, or anything about promoting a yoursundries.store product on Facebook. Trigger even if the user just says "do today's post" or "run the daily FB post" — this skill handles product selection, copywriting in the page's voice, image selection, and publishing via the Facebook Graph API.
---

# Daily Facebook Product Post — Your Sundries Store

Produce exactly **one** Facebook post per run that features a single product from `yoursundries.store`, written in the established voice of the "Your Sundries Store" page, accompanied by the product image and a **Shop Now** call-to-action button that links to the product page.

The run has four stages: **(1) select a product**, **(2) gather its data**, **(3) write the post in the page's voice**, **(4) publish via Graph API**. Do them in order.

---

## Stage 1 — Select the product

Selection follows a strict priority ladder. Walk down it and stop at the first tier that yields a relevant product. Use today's date (the real current date) as the anchor for all date math.

1. **Upcoming special day** — Is there a notable holiday/observance within the next ~10 days (e.g. Valentine's Day, Mother's Day, Father's Day, Memorial Day, Independence Day, Halloween, Thanksgiving, Christmas, New Year, Easter, Mardi Gras, St. Patrick's Day, Cinco de Mayo, Labor Day, Veterans Day)? If so, pick a product that fits that occasion. See `references/calendar.md` for the full list and date rules.
2. **Current or upcoming special month** — e.g. Women's History Month (March), Black History Month (February), Pride Month (June), Breast Cancer Awareness (October), etc. Pick a product that fits the theme. Full list in `references/calendar.md`.
3. **Seasonal fit** — Match the current season (spring/summer/fall/winter) and any active weather mood: gardening and outdoor items in spring, cooling/beach items in summer, cozy/home items in fall, warmth/comfort items in winter.
4. **Random evergreen pick** — If none of the above apply, randomly pick from evergreen categories: pets, babies, children, birthdays, home, kitchen, gifts. Genuinely randomize so the page doesn't repeat the same items.

**Avoiding repeats:** Before finalizing, check `references/post-log.md` (the running log this skill appends to). Do not feature a product posted in the last 14 days. If the top-priority tier only offers a recently-used product, pick a different qualifying product from the same tier before dropping to a lower tier.

State which tier was used and why, so the user can sanity-check the choice.

## Stage 2 — Gather product data (scrape the live site)

The store is a **standard Shopify** site, so use the JSON endpoints rather than parsing HTML — they're stable and complete.

- Full catalog (paginated): `https://yoursundries.store/products.json?limit=250&page=1`
- A single product: `https://yoursundries.store/products/<handle>.json`
- A collection's products: `https://yoursundries.store/collections/<collection-handle>/products.json`

Run `scripts/fetch_products.py` to pull and cache the catalog, then filter by the tier chosen in Stage 1. The script handles pagination and returns title, handle, price, description (body_html stripped to text), tags, product_type, and the primary image URL.

```bash
python scripts/fetch_products.py --query "valentine" --limit 25
```

For the chosen product, capture:
- **Title**
- **Product URL**: `https://yoursundries.store/products/<handle>`
- **Primary image URL** (first image in `images[]`)
- **Short description** (strip HTML, trim to ~1-2 sentences for inspiration — never paste the whole thing)
- **Price** (for your own judgment; per the page convention, do not put the raw price in the post unless existing posts do)

If the JSON endpoint is unreachable, tell the user the site couldn't be reached and that they may need to check the store URL or network access — do not fabricate product details.

## Stage 3 — Write the post in the page's voice

**Match the existing page voice.** Before writing, read `references/voice-guide.md`, which captures the page's established tone from its recent posts. If that file is empty or stale, scrape recent posts first (see `references/voice-guide.md` for how) and update it.

Post construction:
- **Length & tone:** Mirror the recent posts — typically warm, friendly, lightly enthusiastic, short. Don't overhype.
- **Occasion hook:** When the pick came from a holiday/month/season tier, lead with that connection ("Mother's Day is almost here…").
- **Product:** Name it naturally and give one genuine reason to want it. Paraphrase the product description in the page's own words — never copy site copy verbatim.
- **Emoji:** Use them only to the degree the existing posts do.
- **Hashtags:** Match existing posts — include them only if the page already uses them, in the same style/quantity.
- **CTA:** End the message body with a short nudge ("Shop now 👉"). The clickable **Shop Now button** is added structurally in Stage 4, not as plain text — but a brief in-copy nudge is fine if it matches the page style.

Show the drafted copy to the user before publishing unless they've told you to publish without review.

## Stage 4 — Publish via Facebook Graph API

Facebook **link posts do not support a literal "Shop Now" button on organic page posts** — that button type belongs to paid ads / CTA-enabled formats. For an organic post, the equivalent is a **link-attachment post**: posting the product URL produces a clickable link card (image + title + domain) that acts as the shop-now click target, plus the call-to-action wording in the copy. This is the standard, reliable approach. See `references/facebook-publishing.md` for the exact endpoints, the photo-vs-link tradeoff, and how to get a true Shop Now button if the user has a connected ad account.

The page's voice template puts the product URL on its own 🛒 line inside the copy (that's part of its native style — keep it). When you also pass `--link`, Facebook renders the clickable link card from that URL. Pass the **same** product URL to both so the in-copy link and the card point to the same place.

Default publishing method (link post with auto-generated card):

```bash
python scripts/publish_post.py \
  --message "<final copy incl. the 🛒 URL line and hashtags>" \
  --link "https://yoursundries.store/products/<handle>"
```

The script reads credentials from environment variables (`FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`) and calls `POST /{page-id}/feed`. It never hardcodes tokens. If credentials are missing, it prints setup instructions and exits without posting.

After a successful post, **append an entry to `references/post-log.md`** (date, product title, handle, tier used) so future runs avoid repeats.

---

## Run summary

End every run by reporting, in a few lines:
- Which product, and which selection tier triggered it
- The final post copy
- The publish result (post ID, or "drafted only / not published" with the reason)

This keeps the user in control and makes the daily cadence auditable.
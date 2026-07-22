# CLAUDE.md — Sundries Auto-Post

Guidance for Claude Code working in this repository. Read this before making changes.

## What this project is

An autonomous daily Facebook product post for the **Your Sundries Store** page
(`yoursundries.store`, a Shopify store). Once a day it:

1. Scrapes the Shopify catalog (`products.json`)
2. Selects a product via a priority ladder (holiday → month → season → evergreen)
3. Has Claude (Anthropic API) pick the best genuine fit from a shortlist, then write the post copy in the page's voice
4. Publishes a link post (clickable shop card) via the Facebook Graph API
5. Logs the post to avoid repeats within 14 days

Posts publish **live with no pre-approval** by design. The owner operates reactively — deleting any post they dislike. Because of this, guardrails against bad/forced posts matter a lot (see "Hard-won lessons").

## Architecture (deployment shape — critical)

Deployed on **Hetzner + Coolify** from the public GitHub repo `DickHildreth/DailyYourSundriesStorePost`, built via Dockerfile.

**The container idles; a Coolify Scheduled Task does the work.** The entrypoint is
`sleep infinity`. A Coolify Scheduled Task runs `python -m app.main` inside the running
container once a day.

> DO NOT change the entrypoint back to `python -m app.main`. If the container's main
> process posts and exits, Coolify treats it as a crashed service and restarts it in a
> tight loop — posting every few seconds. This actually happened during development and
> spammed the page. The idle-container + scheduled-task split is the fix; keep it.

- No web server, no domain, healthcheck disabled — this is a scheduled job, not a service.
- Persistent volume mounted at `/data` holds the repeat-avoidance log (`post-log.jsonl`).
  Without it, repeat avoidance silently no-ops after each redeploy.
- `TZ` (e.g. `America/Denver`) must be set AND `tzdata` installed in the image (it is, via
  the Dockerfile) or the container stays UTC — skewing both the scheduled time and the
  holiday date math. Note: Coolify's *scheduler* may evaluate cron in its own TZ separately
  from the container clock; verify both after deploy.

## Environment variables

| Var | Purpose |
|-----|---------|
| `FB_PAGE_ID` | `1032436596611484` (the page) |
| `FB_PAGE_ACCESS_TOKEN` | Non-expiring **System User** page token (see below) |
| `ANTHROPIC_API_KEY` | Anthropic API key (copy + product-choice calls) |
| `TZ` | `America/Denver` — drives holiday/season math and run time |
| `POST_LOG_PATH` | `/data/post-log.jsonl` (keep default; must be on the volume) |

## Files

```
app/
  main.py          orchestrator: preflight → catalog → tier cascade → copy → publish → log
  catalog.py       Shopify products.json fetch + simplify
  selection.py     priority ladder, floating-holiday date math, weighted matching,
                   commemorative exclusion, repeat-avoidance filter
  copywriter.py    Anthropic API calls: choose_best_product() + write_post()
                   (the page voice lives in VOICE_SYSTEM_PROMPT here)
  publisher.py     Facebook Graph API link post (v25.0)
  postlog.py       JSONL repeat-avoidance log on /data (14-day window, keyed by handle)
  verify_setup.py  preflight credential checks + container-time diagnostic
  test_selection.py  unit tests for selection/date math (run: python -m app.test_selection)
Dockerfile         installs tzdata; ENTRYPOINT ["sleep","infinity"]
docker-compose.yml
README.md          deployment guide
```

## How selection works (app/selection.py)

`candidate_tiers()` returns an ordered list of `Selection` objects (one per viable tier).
The orchestrator walks them and, for each **occasion** tier, asks Claude
(`copywriter.choose_best_product`) whether any candidate genuinely fits; on `fits=False`
it advances to the next tier. Broad (non-occasion) tiers with a single candidate auto-accept.

Tiers, in priority order:
1a. **Imminent special day** (within `LOOKAHEAD_DAYS`=10) — `is_occasion=True`
1b. **Approaching holiday** (within `APPROACHING_DAYS`=30) where a product **strongly**
    matches (`weighted score >= STRONG_MATCH_MIN`=4) — reserves e.g. a Father's Day
    keychain for Father's Day instead of letting a month tier absorb it. `is_occasion=True`
2.  **Special month** (Pride, Women's History, etc.) — `is_occasion=True`
3.  **Season** — broad, `is_occasion=False`
4.  **Random evergreen** category, then **general catalog pick** — broad, `is_occasion=False`

Key mechanics:
- **Weighted matching** (`weighted_theme_score`): title/tags weighted far above description
  (3/3/2/1) so a product that merely mentions "gift" in its blurb doesn't get mis-claimed.
- **Repeat avoidance**: `fresh_only()` drops handles posted in the last 14 days BEFORE the
  shortlist is built. Keyed on product handle.
- **Commemorative exclusion**: `COMMEMORATIVE_OBSERVANCES` (Juneteenth, Veterans Day,
  Memorial Day) are removed from ALL product-selling tiers — never used as a sales hook.

Tuning levers (all in selection.py): `LOOKAHEAD_DAYS`, `APPROACHING_DAYS`,
`STRONG_MATCH_MIN`, `COMMEMORATIVE_OBSERVANCES`, per-holiday theme keyword lists.

## Hard-won lessons (do not regress these)

These were real failures during development. Each fix exists for a reason.

1. **Idle container + scheduled task** (not entrypoint-posts). Reverting causes a
   post-every-second restart loop. See Architecture above.

2. **Occasion tiers ALWAYS get a fit-check, even with one candidate.** A single weak
   holiday match must be rejectable. An earlier "single candidate → auto-accept" shortcut
   wrongly posted a "Diamond Hardness Tester" as a Father's Day gift. Only *broad* tiers
   auto-accept a lone candidate. Preserve the `is_occasion` flag distinction.

3. **Cascade on `fits=False`** rather than posting the best-of-a-bad-lot. Claude judges
   genuine fit; if no candidate fits an occasion, fall to the next tier.

4. **Commemorative observances are not sales hooks.** A dry run once produced a floral
   grandma shirt wrapped in Juneteenth/African-American-heritage framing — reputationally
   dangerous. Hence `COMMEMORATIVE_OBSERVANCES`. Be cautious adding holidays; think about
   whether selling on them could backfire.

5. **Weight title/tags over description** in matching, or generic keywords in long
   descriptions cause bad occasion claims.

6. **Preflight fails loudly and does not post.** `verify_setup` checks FB token (valid,
   non-expiring, PAGE-type bound to the right page id), Anthropic key, and catalog. Keep
   the FB check using `debug_token` type/profile_id — do NOT query the page node for a
   `tasks` field; that field only exists via a USER token, not a page token (this was a bug).

7. **Graph API version is v25.0.** v21.0 was deprecated and auto-upgraded by Facebook.
   If a response header flags v25.0 deprecated later, bump `GRAPH_VERSION` in publisher.py
   and verify_setup.py.

## Credentials setup (context, mostly one-time)

- **FB token** is a **System User token** from Business Settings → Users → System Users
  (the page is owned by a Business Portfolio, so a user-derived token via `/me/accounts`
  returned empty — the System User route is required). The system user needs BOTH the App
  and the Page assigned as assets with full control. Token expiration set to **Never**.
- **Anthropic key**: pay-as-you-go, billed separately from any Claude subscription. Needs a
  funded balance. Model pinned to `claude-sonnet-4-6`.

## Known operational issues

- **Meta anomaly detection**: a young app posting on a fixed daily schedule tripped an
  "unusual activity" account-confirmation challenge (~4 days after first posts). Cleared via
  the confirmation flow in an incognito window (the in-app button errored on a stale
  session). Durable mitigations: complete **Business Verification** in the Security Center;
  optionally add **time jitter** (post within a 9–11 AM window, not exactly 09:00:00) and/or
  a startup grace period so the app ages before automating. These are not yet implemented.

## Running / testing

```bash
python -m app.test_selection    # unit tests, no network
python -m app.verify_setup      # credential + container-time check, no posting
python -m app.main --dry-run    # full pipeline incl. Claude selection + copy, no publish
python -m app.main              # real: publishes + logs
python -m app.main --skip-preflight   # bypass credential checks
python -m app.verify_setup --quiet    # only prints on failure
```

Always run `--dry-run` after changing selection or the voice prompt, and eyeball the copy —
especially in the days before a major holiday, given live unreviewed posting.

## Conventions

- Stdlib only — no third-party Python deps. Keep it that way (tiny, dependency-free image).
- Fail loudly with non-zero exit so the scheduler surfaces problems instead of silently
  skipping. Never post partial/garbage output.
- The page's voice is defined once, in `VOICE_SYSTEM_PROMPT` (copywriter.py). Edit there.

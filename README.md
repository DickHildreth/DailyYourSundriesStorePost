# Sundries Auto-Post

Autonomous daily Facebook product post for **Your Sundries Store**. Once a day it:

1. Scrapes the Shopify catalog at `yoursundries.store`
2. Picks a product by the priority ladder (special day → special month → season → random evergreen), skipping anything posted in the last 14 days
3. Writes the post copy in the page's voice via the **Anthropic API** (Claude)
4. Publishes a link post (clickable shop card) via the **Facebook Graph API**
5. Logs the post so it isn't repeated

It posts **live with no pre-approval** by design — you operate reactively, deleting any post you don't like from the page.

No third-party Python packages: the app uses only the standard library, so the image is tiny and dependency-free.

---

## Environment variables

| Var | What | Where it comes from |
|-----|------|---------------------|
| `FB_PAGE_ID` | `1032436596611484` | Your page (already determined) |
| `FB_PAGE_ACCESS_TOKEN` | Non-expiring System User token | Business Settings → Users → System Users |
| `ANTHROPIC_API_KEY` | API key for copy generation | console.anthropic.com → API Keys |
| `TZ` | e.g. `America/Denver` | Your timezone — drives holiday/season math + run time |
| `POST_LOG_PATH` | `/data/post-log.jsonl` | Keep default; must sit on a volume |

### On the Anthropic key
If you already call the Anthropic API for another project, you have a billing-enabled
Console account. Create a **separate** key named e.g. `sundries-poster` (Console → API Keys
→ Create Key) so this project's spend and revocation are isolated. Cost is ~a few cents/month
(one short Claude Sonnet completion per day). Model is pinned to `claude-sonnet-4-6`.

---

## Local test

```bash
cp .env.example .env        # fill in real values
set -a; . ./.env; set +a    # load into the shell
python -m app.test_selection   # unit tests (no network)
python -m app.verify_setup     # check all three credentials (no posting)
python -m app.main --dry-run   # full pipeline minus publish: scrapes, selects, writes copy
```

`verify_setup` confirms the FB token is valid + non-expiring + has CREATE_CONTENT on the page,
that the Anthropic key works, and that the catalog is reachable — without posting anything.
`--dry-run` prints the selected product and the generated copy without posting or logging —
use it for the first verification against the live catalog.

When the dry run looks right:

```bash
python -m app.main          # real: publishes and logs
```

---

## Deploy on Coolify

> **Deployment shape (read this first).** This is a run-once job, not a web service.
> The container is deployed as a long-running resource that **idles** (`sleep infinity`),
> and a **Scheduled Task** runs `python -m app.main` inside it once a day. The entrypoint
> deliberately does NOT post on startup — if it did, Coolify would restart the exited
> container in a tight loop and post every few seconds. Do not change the entrypoint back
> to `app.main`.

1. **New Resource → Public Repository**, URL `https://github.com/DickHildreth/DailyYourSundriesStorePost`, branch `main`.
2. **Build Pack: Dockerfile.** Base Directory `/`, Dockerfile Location `/Dockerfile`.
3. **No domain** — leave Domains blank, don't generate one. This isn't a web service.
4. **Disable Healthcheck** (Healthcheck tab). The container idles; no HTTP endpoint to check.
5. **Environment variables:** add the five (below). Mark `FB_PAGE_ACCESS_TOKEN` and
   `ANTHROPIC_API_KEY` as secrets.
6. **Persistent volume:** add a Persistent Storage entry mapping a volume to `/data`
   (keeps the 14-day repeat-avoidance log across redeploys).
7. **Timezone:** set `TZ` (e.g. `America/Denver`) — drives the holiday/season date math and
   the scheduled run time. Without it the container is UTC.
8. **Deploy.** The container starts and idles. **Nothing posts yet** — this is correct.
9. **Verify before scheduling.** Open the resource **Terminal** (or exec in) and run:
   ```
   python -m app.verify_setup     # checks token, API key, catalog — no posting
   python -m app.main --dry-run   # selects + writes copy, still no posting
   ```
   Only when both look right, optionally run one real post: `python -m app.main`.
10. **Scheduled Task:** on the resource's **Scheduled Tasks** tab, add:
    - **Command:** `python -m app.main`
    - **Frequency (cron):** `0 9 * * *` (9 AM daily, container TZ)
    Coolify runs that command inside the idling container once a day. That is the daily post.

### Verifying after deploy
- **Every real run does a pre-flight check first** (FB token valid + non-expiring + CREATE_CONTENT,
  Anthropic key works, catalog reachable). If any check fails, the job prints which one and exits
  without posting. To skip it use `--skip-preflight`; to run only the checks use `--verify-only`.
- Run the scheduled task once manually from Coolify (or `--dry-run` first) and watch the logs.
- A successful run prints `Published. Post ID: <id>`.
- Any failure prints `ERROR: ...` and exits non-zero, so a failed token or unreachable catalog
  is loud in the task logs rather than a silent missed day.

A good first command to run from Coolify after setting env vars:
```
python -m app.verify_setup
```
It validates all three credentials and prints a per-check report.

---

## Egress

The container makes outbound HTTPS to exactly three hosts:
`yoursundries.store`, `graph.facebook.com`, `api.anthropic.com`.
If your Hetzner host or Coolify network has a deny-by-default egress policy, allowlist those
three by domain (Meta and Anthropic use rotating CDN IPs, so don't pin IPs).

## Files

```
app/
  main.py          orchestrator (entrypoint)
  catalog.py       Shopify catalog fetch
  selection.py     priority-ladder selection + date math
  copywriter.py    Anthropic API call (voice prompt lives here)
  publisher.py     Facebook Graph API link post
  postlog.py       JSONL repeat-avoidance log on /data
  verify_setup.py  pre-flight credential checks (FB token, Anthropic key, catalog)
  test_selection.py  unit tests for the selection logic
Dockerfile
docker-compose.yml
.env.example
```

## Tuning the voice
The page voice lives in `VOICE_SYSTEM_PROMPT` in `app/copywriter.py`. Edit it there to adjust
tone, structure, hashtag style, etc. Re-deploy to apply.

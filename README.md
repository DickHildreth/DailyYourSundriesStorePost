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

1. **New Resource → Docker Compose** (or Dockerfile), pointed at this repo/folder.
2. **Environment variables:** add the five above in Coolify's env UI. Mark
   `FB_PAGE_ACCESS_TOKEN` and `ANTHROPIC_API_KEY` as secrets.
3. **Persistent volume:** the compose file declares a named volume `sundries_data`
   mounted at `/data`. Coolify will create it. This is what makes the 14-day repeat-avoidance
   log survive restarts/redeploys. If you configure storage manually in the Coolify UI instead,
   add a **Persistent Storage** entry mapping a volume to `/data`.
4. **Timezone:** set `TZ` (e.g. `America/Denver`) as an env var — the container's clock drives
   both the "upcoming holiday within 10 days" logic and the scheduled run time. Without it the
   container defaults to UTC and the date math will be off by your offset.
5. **Schedule:** use Coolify's **Scheduled Tasks** for this resource. Add a task with:
   - **Command:** `python -m app.main`
   - **Frequency (cron):** e.g. `0 9 * * *` for 9:00 AM daily (in the container's TZ)
   The container runs, posts once, logs, and exits. `restart: "no"` keeps it from looping.

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

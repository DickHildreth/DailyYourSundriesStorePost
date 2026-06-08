FROM python:3.12-slim

# tzdata lets the container honor the TZ env var (e.g. America/Denver). Without it,
# the slim image can't resolve named timezones and silently stays on UTC — which
# skews both the scheduled run time and the holiday "days until" date math.
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

# No third-party Python deps — the app uses only the stdlib.
WORKDIR /app
COPY app ./app

# Persistent log lives here; mount a volume at /data in Coolify.
ENV POST_LOG_PATH=/data/post-log.jsonl
RUN mkdir -p /data

# IMPORTANT — deployment shape:
# This image is deployed in Coolify as a long-running resource, but it must NOT
# post on startup. If the entrypoint ran `python -m app.main`, the container would
# post once, exit, and Coolify would restart it in a tight loop — posting every few
# seconds. So the resident container simply idles. The actual daily post is run by a
# Coolify *Scheduled Task* that executes `python -m app.main` inside this container
# once per day (e.g. cron `0 9 * * *`).
#
# To run the post manually (verify / dry-run / one real post), exec into the
# container:  python -m app.verify_setup   |   python -m app.main --dry-run   |   python -m app.main
ENTRYPOINT ["sleep", "infinity"]

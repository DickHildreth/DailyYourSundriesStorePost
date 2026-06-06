FROM python:3.12-slim

# No third-party deps — the app uses only the Python stdlib.
WORKDIR /app
COPY app ./app

# Persistent log lives here; mount a volume at /data in Coolify.
ENV POST_LOG_PATH=/data/post-log.jsonl
RUN mkdir -p /data

# Default command runs one post. The scheduler invokes this once per day.
ENTRYPOINT ["python", "-m", "app.main"]

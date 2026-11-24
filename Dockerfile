FROM python:3.13-slim

# ffmpeg: merging/converting media; deno: JS runtime yt-dlp needs for YouTube
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot ./bot

ENV PYTHONUNBUFFERED=1 DATA_DIR=/app/data
VOLUME /app/data
CMD ["python", "-m", "bot"]

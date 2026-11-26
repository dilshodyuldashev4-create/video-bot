#!/bin/sh
# YouTube changes often and old yt-dlp versions stop downloading. Docker keeps the version from
# the image build (pip layer is cached), so update it on every start. Failing is fine: the bot
# then runs with the version it has.
timeout 120 pip install --no-cache-dir -q -U --pre "yt-dlp[default]" bgutil-ytdlp-pot-provider \
  || echo "yt-dlp update skipped"
exec python -m bot

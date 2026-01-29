#!/usr/bin/env bash
set -euo pipefail

POSTBACK_LOG="${POSTBACK_LOG:-/app/data/postback.log}"

cleanup() {
  if [[ -n "${POSTBACK_PID:-}" ]]; then
    kill "$POSTBACK_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT

echo "==> Starting PocketOption postback server..."
python -m bot.services.pocketoption.postback &
POSTBACK_PID=$!

echo "==> Starting Telegram bot..."
python -m bot.main

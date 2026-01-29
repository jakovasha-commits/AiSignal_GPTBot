#!/usr/bin/env bash
set -euo pipefail

HOST="root@195.179.193.173"
REMOTE_DIR="/root/tradingbot"
PROJECT_NAME="tradingbot"

EXCLUDES=(
  --exclude ".git/"
  --exclude ".venv/"
  --exclude "__pycache__/"
  --exclude "*.pyc"
  --exclude "*.pyo"
  --exclude "*.log"
  --exclude ".DS_Store"
  --exclude "node_modules/"
  --exclude ".idea/"
  --exclude ".vscode/"
  --exclude "*.zip"
  --exclude "data/"
)

echo "==> Rsync project to server..."
rsync -avz --delete "${EXCLUDES[@]}" ./ "$HOST:$REMOTE_DIR/"

echo "==> Deploy via Docker on server..."
ssh "$HOST" bash -s <<'EOSSH'
set -euo pipefail

REMOTE_DIR="/root/tradingbot"
PROJECT_NAME="tradingbot"

cd "$REMOTE_DIR"

echo "==> Ensure data directory for logs exists and writable"
mkdir -p data/ai_logs
chmod 777 data
chmod 777 data/ai_logs

echo "==> Ensure .env exists (not overwriting)..."
if [[ ! -f ".env" ]]; then
  cat > .env <<'EOF'

EOF
  chmod 600 .env
  echo "Создан /root/tradingbot/.env (шаблон). Заполни и перезапусти деплой."
fi

echo "==> Ensure Docker + Compose plugin..."
command -v docker >/dev/null 2>&1 || { echo "ERROR: Docker не установлен."; exit 1; }

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "ERROR: Не найден docker compose (plugin) или docker-compose."
  exit 1
fi

echo "==> Stop old systemd service (just in case, no codim touched)..."
systemctl stop tradingbot 2>/dev/null || true
systemctl disable tradingbot 2>/dev/null || true

echo "==> Recreate container from compose..."
$COMPOSE -p "$PROJECT_NAME" down --remove-orphans || true

docker rm -f tradingbot 2>/dev/null || true

$COMPOSE -p "$PROJECT_NAME" up -d --build

echo "==> Status:"
$COMPOSE -p "$PROJECT_NAME" ps

echo "==> Last logs:"
$COMPOSE -p "$PROJECT_NAME" logs --tail=150
EOSSH

echo "==> Done."

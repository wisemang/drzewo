#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 4 ]]; then
  echo "Usage: $0 <city> <file> [env_file=.env.prod] [ssh_host=drzewo-user]"
  exit 1
fi

CITY="$1"
DATA_FILE="$2"
ENV_FILE="${3:-.env.prod}"
SSH_HOST="${4:-drzewo-user}"
LOCAL_PORT="${DRZEWO_TUNNEL_LOCAL_PORT:-6543}"
TUNNEL_PID=""

cleanup() {
  if [[ -n "$TUNNEL_PID" ]]; then
    kill "$TUNNEL_PID" >/dev/null 2>&1 || true
    wait "$TUNNEL_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE"
  exit 1
fi

if [[ ! -f "$DATA_FILE" ]]; then
  echo "Data file not found: $DATA_FILE"
  exit 1
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv/bin/python. Run 'make setup' first."
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

: "${DRZEWO_DB:=drzewo}"
: "${DRZEWO_DB_USER:?DRZEWO_DB_USER is required in $ENV_FILE}"
: "${DRZEWO_DB_PW:?DRZEWO_DB_PW is required in $ENV_FILE}"
: "${DRZEWO_DB_HOST:=127.0.0.1}"
: "${DRZEWO_DB_PORT:=5432}"

if [[ "$DRZEWO_DB_HOST" == "127.0.0.1" || "$DRZEWO_DB_HOST" == "localhost" ]]; then
  echo "Starting SSH tunnel via $SSH_HOST on local port $LOCAL_PORT..."
  ssh -N -L "${LOCAL_PORT}:127.0.0.1:5432" "$SSH_HOST" &
  TUNNEL_PID="$!"
  sleep 1
  DRZEWO_DB_HOST="127.0.0.1"
  DRZEWO_DB_PORT="$LOCAL_PORT"
fi

echo "Loading city '$CITY' from '$DATA_FILE'..."
.venv/bin/python tree_loader.py "$CITY" --file "$DATA_FILE"

declare -A SOURCE_NAMES
SOURCE_NAMES=(
  [toronto]="Toronto Open Data Street Trees"
  [ottawa]="Ottawa Open Data Tree Inventory"
  [montreal]="Montreal Open Data Tree Inventory"
  [calgary]="Calgary Open Data Tree Inventory"
  [waterloo]="Waterloo Open Data Tree Inventory"
  [boston]="Boston Open Data Tree Inventory"
)

SOURCE_NAME="${SOURCE_NAMES[$CITY]:-}"
if [[ -n "$SOURCE_NAME" ]]; then
  echo "Verifying row count for source: $SOURCE_NAME"
  PGPASSWORD="$DRZEWO_DB_PW" psql \
    "host=$DRZEWO_DB_HOST port=$DRZEWO_DB_PORT dbname=$DRZEWO_DB user=$DRZEWO_DB_USER" \
    -c "SELECT source, COUNT(*) FROM street_trees WHERE source = '$SOURCE_NAME' GROUP BY source;"
else
  echo "No source-name mapping for city '$CITY'; skipping verification query."
fi

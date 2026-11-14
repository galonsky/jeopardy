#!/usr/bin/env bash
set -uo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

batch_size="${CODEX_CLASSIFY_BATCH_SIZE:-500}"
initial_batch_size="$batch_size"
timeout_seconds="${CODEX_CLASSIFY_TIMEOUT:-3600}"
max_stalled_retries="${CODEX_CLASSIFY_MAX_STALLED_RETRIES:-3}"
stalled_retries=0

pending_count() {
  uv run python backend/manage.py shell -c \
    'from clues.models import SourceClue; print(SourceClue.objects.exclude(classifications__version="v1").count())' \
    | tail -n 1
}

if [[ -n "${CODEX_CLASSIFY_WAIT_FOR_PID:-}" ]]; then
  while ps -p "$CODEX_CLASSIFY_WAIT_FOR_PID" -o args= 2>/dev/null \
    | grep -Fq 'backend/manage.py classify_clues_codex'; do
    sleep 30
  done
fi

while true; do
  before="$(pending_count)" || exit 2
  if [[ "$before" == "0" ]]; then
    echo "No pending clues remain."
    exit 0
  fi

  echo "Starting Codex classification pass: $before pending, batch size $batch_size."
  uv run python backend/manage.py classify_clues_codex \
    --batch-size "$batch_size" \
    --timeout "$timeout_seconds"
  command_status=$?

  after="$(pending_count)" || exit 2
  echo "Pass finished with status $command_status: $after pending."
  if [[ "$after" == "0" ]]; then
    echo "All clues are classified."
    exit 0
  fi

  if (( after < before )); then
    stalled_retries=0
    if (( batch_size != initial_batch_size )); then
      batch_size="$initial_batch_size"
      echo "Progress resumed; restoring batch size $batch_size."
    fi
    continue
  fi

  if (( batch_size > 1 )); then
    batch_size=$(((batch_size + 1) / 2))
    stalled_retries=0
    echo "No rows saved; retrying with smaller batch size $batch_size."
    continue
  fi

  stalled_retries=$((stalled_retries + 1))
  if (( stalled_retries >= max_stalled_retries )); then
    echo "Stopped after $stalled_retries no-progress retries; $after clues remain pending." >&2
    exit 1
  fi
  echo "No rows saved; retry $stalled_retries/$max_stalled_retries in 30 seconds."
  sleep 30
done

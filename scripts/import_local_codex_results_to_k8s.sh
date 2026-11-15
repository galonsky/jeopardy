#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

namespace="${CODEX_IMPORT_NAMESPACE:-jeopardy}"
deployment="${CODEX_IMPORT_DEPLOYMENT:-jeopardy-api}"
container="${CODEX_IMPORT_CONTAINER:-api}"
remote_script="/tmp/jeopardy-import-codex-classifications.py"
payload_file=""

cleanup() {
  if [[ -n "$payload_file" ]]; then
    rm -f "$payload_file"
  fi
  kubectl exec -n "$namespace" "deploy/$deployment" -c "$container" -- rm -f "$remote_script" \
    >/dev/null 2>&1 || true
}
trap cleanup EXIT

if [[ -n "${CODEX_CLASSIFY_WAIT_FOR_PID:-}" ]]; then
  echo "Waiting for local classification process $CODEX_CLASSIFY_WAIT_FOR_PID to finish."
  while ps -p "$CODEX_CLASSIFY_WAIT_FOR_PID" -o args= 2>/dev/null \
    | grep -Fq "scripts/run_codex_classification_until_stalled.sh"; do
    sleep 30
  done
fi

payload_file="$(mktemp /tmp/jeopardy-codex-classifications.XXXXXX.jsonl)"
uv run python scripts/export_codex_classifications.py > "$payload_file"
echo "Exported $(wc -l < "$payload_file") local Codex classifications."

kubectl exec -i -n "$namespace" "deploy/$deployment" -c "$container" -- \
  sh -c "cat > '$remote_script'" < scripts/import_codex_classifications.py
kubectl exec -i -n "$namespace" "deploy/$deployment" -c "$container" -- \
  python "$remote_script" < "$payload_file"

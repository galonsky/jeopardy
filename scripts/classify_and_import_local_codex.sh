#!/usr/bin/env bash
set -uo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

classification_status=0
import_status=0

echo "Starting resilient local Codex classification."
uv run python scripts/classify_codex_pending_resilient.py || classification_status=$?
echo "Local classifier exited with status $classification_status. Importing saved results."

scripts/import_local_codex_results_to_k8s.sh || import_status=$?
echo "Import exited with status $import_status."

if (( import_status != 0 )); then
  exit "$import_status"
fi
exit "$classification_status"

#!/usr/bin/env sh
# Run validate + check on every domain pack, including the hidden engine smoke pack. Add --pg to include PostgreSQL.
set -e
cd "$(dirname "$0")/.."
status=0
for d in domains/*/; do
  name=$(basename "$d")
  [ -f "$d/domain.toml" ] || continue
  echo "== $name"
  python3 -m dsgen "$name" validate || status=1
  python3 -m dsgen "$name" check --quiet "$@" 2>&1 | grep -E "checks passed|ALL CHECKS|CHECK FAILED|FAIL|Traceback" || true
  python3 -m dsgen "$name" check --quiet "$@" >/dev/null 2>&1 || status=1
  python3 scripts/snapshot_check.py "$name" || status=1   # committed snapshot must match the pack
done
find . -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
exit $status

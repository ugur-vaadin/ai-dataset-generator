#!/usr/bin/env sh
# Run validate + check on every domain pack, including the hidden engine smoke pack. Add --pg to include PostgreSQL.
set -e
cd "$(dirname "$0")/.."
mkdir -p out          # a fresh clone has no out/ yet; the per-pack log below is written there
status=0
for d in domains/*/; do
  name=$(basename "$d")
  [ -f "$d/domain.toml" ] || continue
  echo "== $name"
  python3 -m dsgen "$name" validate || status=1
  log="out/_test_$name.log"
  if python3 -m dsgen "$name" check --quiet "$@" >"$log" 2>&1; then :; else status=1; fi
  grep -E "checks passed|ALL CHECKS|CHECK FAILED|FAIL|Traceback" "$log" || true
  rm -f "$log"
  python3 scripts/snapshot_check.py "$name" || status=1   # committed snapshot must match the pack
  # optional config overlays shipped with the pack (e.g. the messy-data pass) must pass the same checks
  for ov in "$d"config-*.toml; do
    [ -f "$ov" ] || continue
    if python3 -m dsgen "$name" check --quiet --config "$ov" --out "out/_matrix/$name" >/dev/null 2>&1; then
      echo "overlay $(basename "$ov") ok"
    else
      echo "overlay $(basename "$ov") FAILED"; status=1
    fi
  done
  # regeneration must hold on any "today": first working day, month end, and a first-of-month after a weekend
  for d in 2026-10-01 2026-10-30 2027-03-01; do
    if python3 -m dsgen "$name" check --quiet --as-of "$d" --out "out/_matrix/$name" >/dev/null 2>&1; then
      echo "as-of $d ok"
    else
      echo "as-of $d FAILED"; status=1
    fi
  done
done
rm -rf out/_matrix
find . -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
exit $status

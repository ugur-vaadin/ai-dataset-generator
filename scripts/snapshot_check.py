"""Fail when a committed snapshot (datasets/<domain>) no longer matches a fresh generation (out/<domain>).
Called by scripts/test.sh after each pack's check; compares the per-table SHA-256 in both manifests."""
import json
import os
import sys

n = sys.argv[1]
snap = f"datasets/{n}/manifest.json"
if not os.path.exists(snap):
    sys.exit(0)
a = json.load(open(f"out/{n}/manifest.json", encoding="utf-8"))["csv_sha256"]
b = json.load(open(snap, encoding="utf-8"))["csv_sha256"]
bad = sorted(t for t in set(a) | set(b) if a.get(t) != b.get(t))
if bad:
    print(f"snapshot datasets/{n}: STALE, differs in {', '.join(bad)} -> run scripts/snapshot.sh {n}")
    sys.exit(1)
print(f"snapshot datasets/{n}: up to date")

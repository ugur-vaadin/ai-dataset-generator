#!/usr/bin/env sh
# Publish a domain's generated dataset into datasets/<domain>/ — the committed snapshot the demo application
# and colleagues use without running the generator. Always produced by the tool, never edited by hand.
#   scripts/snapshot.sh nordic_supply            # regenerate + check into datasets/nordic_supply
#   scripts/snapshot.sh nordic_supply --pg       # also smoke-test PostgreSQL
# The H2 database file, cost estimate, review queue and usage log are generated too but git-ignored
# (see .gitignore); rebuild the H2 file with: python3 -m dsgen <domain> generate --out datasets/<domain> --h2-file
set -e
cd "$(dirname "$0")/.."
name="${1:?usage: scripts/snapshot.sh <domain> [check flags]}"; shift
out="datasets/$name"
python3 -m dsgen "$name" check --out "$out" --csv-path-prefix "./$out/csv" "$@"
python3 scripts/snapshot_readme.py "$name" "$out"

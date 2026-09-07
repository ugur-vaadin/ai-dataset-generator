"""Smoke test against a real PostgreSQL in Docker: DDL, \\copy loader, read-only role, smoke queries,
denied writes. Needs a running Docker daemon; skips cleanly otherwise."""
from __future__ import annotations

import os
import shutil
import subprocess
import time

IMAGE = os.environ.get("DSGEN_PG_IMAGE", "postgres:16-alpine")


def _docker(*args, **kw):
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=600, **kw)


def run(domain, out: str) -> dict:
    if not shutil.which("docker") or _docker("info").returncode != 0:
        return {"status": "skipped", "detail": "docker not available"}
    spec = domain.spec
    out = os.path.abspath(out)
    name = f"dsgen-pg-{os.getpid()}"
    r = _docker("run", "-d", "--rm", "--name", name, "-e", "POSTGRES_PASSWORD=pw", "-e", "POSTGRES_DB=demo",
                "-v", f"{out}:/data:ro", IMAGE)
    if r.returncode != 0:
        return {"status": "skipped", "detail": f"could not start {IMAGE}: {r.stderr.strip()[:200]}"}
    try:
        for _ in range(60):
            if _docker("exec", name, "pg_isready", "-U", "postgres", "-d", "demo").returncode == 0:
                break
            time.sleep(1)
        else:
            return {"status": "failed", "detail": "postgres did not become ready"}
        def psql(user, password, args):
            return _docker("exec", "-e", f"PGPASSWORD={password}", name, "psql", "-v", "ON_ERROR_STOP=1", "-U", user, "-d", "demo", "-q", "-t", "-A", *args)
        # the loader uses \copy with the CSV prefix of the host; rewrite to the mounted path
        loader = open(os.path.join(out, "sql", "load-postgres.sql"), encoding="utf-8").read()
        prefix = next(l for l in loader.splitlines() if l.startswith("\\copy")).split("FROM '")[1].rsplit("/", 1)[0]
        loader = loader.replace(prefix, "/data/csv")
        _docker("exec", "-i", name, "sh", "-c", "cat > /tmp/load.sql", input=loader)
        for step, script in (("schema", "-f /data/sql/schema-postgres.sql"), ("load", "-f /tmp/load.sql"), ("readonly", "-f /data/sql/readonly-user-postgres.sql")):
            r = psql("postgres", "pw", script.split())
            if r.returncode != 0:
                return {"status": "failed", "detail": f"{step}: {(r.stderr or r.stdout).strip()[:500]}"}
        queries = {f"count {t}": f"SELECT COUNT(*) FROM {t}" for t in spec.exposed_tables[:3]}
        queries.update({f"view {v}": f"SELECT COUNT(*) FROM {v}" for v in spec.views})
        for sq in domain.checks.get("smoke", []):
            queries[sq["name"]] = sq.get("sql_postgres", sq["sql"])
        results = {}
        for qn, sql in queries.items():
            r = psql("ai_reader", "ai_reader", ["-c", sql])
            results[qn] = {"ok": r.returncode == 0, "first_line": (r.stdout.strip().splitlines() or [""])[0] if r.returncode == 0 else r.stderr.strip()[:300]}
        t0 = spec.exposed_tables[0]
        denied = {"ai_reader cannot UPDATE": f"UPDATE {t0} SET {spec.column_names(t0)[1]} = {spec.column_names(t0)[1]} WHERE false"}
        if spec.hidden_tables:
            denied[f"ai_reader cannot read {spec.hidden_tables[0]}"] = f"SELECT COUNT(*) FROM {spec.hidden_tables[0]}"
        for qn, sql in denied.items():
            r = psql("ai_reader", "ai_reader", ["-c", sql])
            ok = r.returncode != 0 and "permission denied" in r.stderr
            results[qn] = {"ok": ok, "first_line": "denied" if ok else (r.stdout + r.stderr).strip()[:300]}
        failed = [k for k, v in results.items() if not v["ok"]]
        return {"status": "failed" if failed else "ok", "detail": IMAGE + (f"; failed: {failed}" if failed else ""), "queries": results}
    finally:
        _docker("rm", "-f", name)

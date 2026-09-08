"""Smoke test against a real H2 database: DDL, CSVREAD loader, read-only user, the domain's smoke
queries. Needs `java` and an H2 jar (env H2_JAR, or the newest in ~/.m2). Skips cleanly otherwise."""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile


def find_h2_jar():
    if os.environ.get("H2_JAR") and os.path.exists(os.environ["H2_JAR"]):
        return os.environ["H2_JAR"]
    cands = [c for c in glob.glob(os.path.expanduser("~/.m2/repository/com/h2database/h2/*/h2-*.jar")) if "sources" not in c and "javadoc" not in c]
    return sorted(cands)[-1] if cands else None

def absolute_loader(out: str) -> str:
    """The committed loader may reference the CSV directory by a relative path (--csv-path-prefix); the
    smoke test and the H2 file builder run Java elsewhere, so they load through a temporary copy that
    points at the absolute csv/ directory of this output folder."""
    import re
    src = os.path.join(out, "sql", "load-h2.sql")
    csv_dir = os.path.abspath(os.path.join(out, "csv")).replace("\\", "/")
    text = re.sub(r"CSVREAD\('[^']*/([^/']+\.csv)'", lambda m: f"CSVREAD('{csv_dir}/{m.group(1)}'", open(src, encoding="utf-8").read())
    tmp = os.path.join(tempfile.mkdtemp(prefix="dsgen-load-"), "load-h2.sql")
    open(tmp, "w", encoding="utf-8").write(text)
    return tmp

def _run(jar, args, cwd):
    return subprocess.run(["java", "-cp", jar] + args, cwd=cwd, capture_output=True, text=True, timeout=600)

def run(domain, out: str) -> dict:
    """Returns {'status': 'ok'|'failed'|'skipped', 'detail': str, 'queries': {...}}."""
    jar = find_h2_jar()
    if not jar or not shutil.which("java"):
        return {"status": "skipped", "detail": "no java or H2 jar found (set H2_JAR)"}
    spec = domain.spec
    tmp = tempfile.mkdtemp(prefix="dsgen-h2-")
    url = f"jdbc:h2:{tmp}/db"
    out = os.path.abspath(out)
    try:
        for name, script in (("schema", os.path.join(out, "sql/schema-h2.sql")), ("load", absolute_loader(out)), ("readonly-user", os.path.join(out, "sql/readonly-user-h2.sql"))):
            r = _run(jar, ["org.h2.tools.RunScript", "-url", url, "-user", "sa", "-script", script], out)
            if r.returncode != 0:
                return {"status": "failed", "detail": f"{name}: {r.stderr.strip()[:500]}"}
        queries = {f"count {t}": f"SELECT COUNT(*) FROM {t}" for t in spec.exposed_tables[:3]}
        queries.update({f"view {v}": f"SELECT COUNT(*) FROM {v}" for v in spec.views})
        for sq in domain.checks.get("smoke", []):
            queries[sq["name"]] = sq["sql"]
        results = {}
        ro = ["org.h2.tools.Shell", "-url", url, "-user", "ai_reader", "-password", "ai_reader", "-sql"]
        for name, sql in queries.items():   # as the read-only user, so the grants are tested too
            r = _run(jar, ro + [sql], out)
            ok = r.returncode == 0 and "Error" not in r.stdout and "Exception" not in r.stderr
            first = next((l for l in r.stdout.splitlines() if l.strip() and not l.startswith("(")), "")
            results[name] = {"ok": ok, "first_line": first if ok else (r.stdout + r.stderr).strip()[:300]}
        denied = {"ai_reader cannot UPDATE": f"UPDATE {spec.exposed_tables[0]} SET {spec.column_names(spec.exposed_tables[0])[1]} = {spec.column_names(spec.exposed_tables[0])[1]} WHERE 1=0"}
        if spec.hidden_tables:
            denied[f"ai_reader cannot read {spec.hidden_tables[0]}"] = f"SELECT COUNT(*) FROM {spec.hidden_tables[0]}"
        for name, sql in denied.items():
            r = _run(jar, ro + [sql], out)
            was_denied = "Not enough rights" in (r.stdout + r.stderr) or "not found" in (r.stdout + r.stderr)
            results[name] = {"ok": was_denied, "first_line": "denied" if was_denied else (r.stdout + r.stderr).strip()[:300]}
        failed = [k for k, v in results.items() if not v["ok"]]
        return {"status": "failed" if failed else "ok", "detail": f"h2 jar {os.path.basename(jar)}" + (f"; failed: {failed}" if failed else ""), "queries": results}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

"""Build a ready-to-use H2 database file (out/db/<domain>.mv.db) from the DDL, loader and read-only
user, so an application can ship the database instead of loading CSVs at startup."""
from __future__ import annotations

import os
import shutil
import subprocess

from .h2check import find_h2_jar


def build(domain, out: str) -> dict:
    jar = find_h2_jar()
    if not jar or not shutil.which("java"):
        return {"status": "skipped", "detail": "no java or H2 jar found (set H2_JAR)"}
    out = os.path.abspath(out)
    db_dir = os.path.join(out, "db")
    os.makedirs(db_dir, exist_ok=True)
    base = os.path.join(db_dir, domain.name)
    for f in (f"{base}.mv.db", f"{base}.trace.db"):
        if os.path.exists(f):
            os.remove(f)
    url = f"jdbc:h2:{base}"
    for script in ("schema-h2.sql", "load-h2.sql", "readonly-user-h2.sql"):
        r = subprocess.run(["java", "-cp", jar, "org.h2.tools.RunScript", "-url", url, "-user", "sa", "-script", os.path.join(out, "sql", script)],
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            return {"status": "failed", "detail": f"{script}: {r.stderr.strip()[:300]}"}
    size = os.path.getsize(f"{base}.mv.db")
    return {"status": "ok", "detail": f"{os.path.relpath(base + '.mv.db')} ({size / 1e6:.1f} MB); JDBC URL jdbc:h2:file:./db/{domain.name} (user sa, or ai_reader for the AI)"}

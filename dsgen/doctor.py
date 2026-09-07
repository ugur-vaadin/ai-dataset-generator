"""Environment check: what this machine can run, without printing any secret."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

from .h2check import find_h2_jar


def run() -> int:
    rows = []
    ok = sys.version_info >= (3, 11)
    rows.append(("Python 3.11+", ok, sys.version.split()[0]))
    try:
        import PIL  # noqa
        rows.append(("Pillow (placeholder images)", True, "installed"))
    except ImportError:
        rows.append(("Pillow (placeholder images)", False, "missing: placeholder images are skipped; pip install pillow"))
    java = shutil.which("java")
    jar = find_h2_jar()
    rows.append(("Java + H2 jar (H2 smoke test, --h2-file)", bool(java and jar), f"{'java ok' if java else 'no java'}; {'jar ' + os.path.basename(jar) if jar else 'no H2 jar (set H2_JAR)'}"))
    docker = shutil.which("docker") and subprocess.run(["docker", "info"], capture_output=True).returncode == 0
    rows.append(("Docker (PostgreSQL smoke test, --pg)", bool(docker), "running" if docker else "not available; --pg is skipped"))
    for var, prov in (("OPENAI_API_KEY", "openai"), ("GOOGLE_API_KEY", "google")):
        present = bool(os.environ.get(var))
        rows.append((f"{var} (--images {prov})", present, "set (value not shown)" if present else "not set; --images " + prov + " falls back to the placeholder"))
    width = max(len(r[0]) for r in rows)
    for name, good, detail in rows:
        print(f"{'ok  ' if good else 'warn'} {name:<{width}}  {detail}")
    print("\nMinimum for generate + verify: Python 3.11+. Everything else is optional and skipped when missing.")
    return 0

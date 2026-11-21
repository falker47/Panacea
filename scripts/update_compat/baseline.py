"""Compare Linux fixture failures by test ID; retain raw logs for both revisions."""

import json
import os
from pathlib import Path
import re
import subprocess
import sys


def capture(root, output):
    output.mkdir(parents=True, exist_ok=True)
    tools = {
        "pytest": ["-m", "pytest", "-q", "tests", "-rfE"],
        "qt": ["-m", "unittest", "discover", "-s", "qt_app/tests", "-p", "test_*.py"],
    }
    failures = {}
    for name, args in tools.items():
        log = output / (name + ".log")
        cache = output / "pytest-cache"
        if name == "pytest":
            args += ["-o", f"cache_dir={cache}"]
        with log.open("wb") as stream:
            result = subprocess.run([sys.executable, *args], cwd=root, stdout=stream,
                                    stderr=subprocess.STDOUT, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
        text = log.read_text(encoding="utf-8", errors="replace")
        if name == "pytest":
            lastfailed = cache / "v/cache/lastfailed"
            ids = sorted(json.loads(lastfailed.read_bytes())) if lastfailed.exists() else []
        else:
            ids = sorted(set(re.findall(r"^(?:FAIL|ERROR): (.*)$", text, re.MULTILINE)))
        if result.returncode and (result.returncode != 1 or not ids):
            raise RuntimeError(f"{name} did not finish normally; inspect {log}")
        failures[name] = ids
    (output / "failures.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    return failures


def main():
    previous = Path(sys.argv[1])
    root = Path.cwd()
    output = root / "build/update-compat/linux"
    before = capture(previous, output / "base")
    after = capture(root, output / "head")
    new = {k: sorted(set(after[k]) - set(before[k])) for k in before}
    if any(new.values()):
        raise SystemExit(f"New Linux failures: {new}")


if __name__ == "__main__":
    main()

"""Collect all matrix rows, including explicit missing or failed reports."""

import json
import os
from pathlib import Path

from scripts.update_compat.published import PUBLISHED


def main():
    successful = True
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
        summary.write("| Published client | Canonical | Lower-case (informational) | Gate |\n|---|---|---|---|\n")
        for tag in PUBLISHED:
            path = Path("reports") / f"client-{tag}.json"
            data = json.loads(path.read_bytes()) if path.exists() else {}
            canonical = data.get("canonical", {}).get("result", "missing")
            lower = data.get("lower", {}).get("result", "n/a")
            status = data.get("status", "missing")
            if data.get("sha") != os.environ["SOURCE_SHA"] or status != "PASS":
                successful = False
            summary.write(f"| {tag} | {canonical} | {lower} | {status} |\n")
    if not successful:
        raise SystemExit("One or more pinned clients lack a passing exact-SHA report")


if __name__ == "__main__":
    main()

"""Test pinned PYZ clients against streamed candidate bytes on a disposable runner."""

import argparse
import json
import os
from pathlib import Path
import tempfile

from scripts.release_tools import binary_sha256
from scripts.update_compat.github_emulator import ReleaseFixture
from scripts.update_compat.hosted import hosted_guard, published_modules, report
from scripts.update_compat.published import PUBLISHED


def evaluate(old, fixture, destination, expected):
    module = old["modules.updater"]
    config = old["version"]
    client = module.UpdateClient(config.GITHUB_REPO, config.VERSION, opener=fixture.open)
    try:
        release = client.check()
    except module.UpdateManifestError as error:
        return {"result": "reject", "reason": str(error)}
    if release is None or "v" + release.version != fixture.manifest["tag_name"]:
        raise RuntimeError("Candidate version was not offered")
    downloaded = client.download(release, destination)
    if binary_sha256(downloaded) != expected:
        raise RuntimeError("Downloaded bytes differ from the candidate")
    return {"result": "accept", "sha256": expected}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tag", choices=PUBLISHED)
    tag = parser.parse_args().tag
    temp, _ = hosted_guard()
    artifacts = Path("build/candidate")
    canonical = "error"
    lower = "n/a"
    try:
        with report(f"client-{tag}") as data:
            meta = json.loads((artifacts / "candidate.json").read_text(encoding="utf-8-sig"))
            if meta["sha"] != os.environ["SOURCE_SHA"]:
                raise RuntimeError("Candidate belongs to a different SHA")
            legacy = tag in {"v2.0.0", "v2.0.1"}
            with published_modules(Path("build/published/Panacea.exe"), tag) as old:
                for variant in (("canonical", "lower") if legacy else ("canonical",)):
                    fixture = ReleaseFixture(artifacts, "v" + meta["version"], lower_case=variant == "lower")
                    data[variant] = {"requests": fixture.requests}
                    try:
                        with tempfile.TemporaryDirectory(dir=temp) as directory:
                            outcome = evaluate(old, fixture, directory, meta["exe_sha256"])
                    except Exception as error:
                        if variant != "lower":
                            raise
                        outcome = {"result": "error", "reason": str(error)}
                    data[variant].update(outcome)
                canonical = data["canonical"]["result"]
                lower = data.get("lower", {}).get("result", "n/a")
                if legacy:
                    if canonical != "reject" or "outside the configured repository" not in data["canonical"]["reason"]:
                        raise RuntimeError("Expected the published repository-capitalization rejection")
                elif canonical != "accept":
                    raise RuntimeError("Supported release refused the candidate")
    finally:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(f"| Published client | Canonical | Lower-case (informational) |\n"
                      f"|---|---|---|\n| {tag} | {canonical} | {lower} |\n")


if __name__ == "__main__":
    main()

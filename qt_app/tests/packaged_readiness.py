"""Measure the real one-file Qt readiness acknowledgement on a disposable CI runner."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def measure(candidate: Path):
    from scripts.hosted_installer_probe import disposable_guard
    from scripts.hosted_windows_release_probe import _kill_only_child, verified_upgrade_ready
    from modules.update_install import install_verified

    if os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        raise RuntimeError("This fixture requires a GitHub-hosted disposable runner")
    runner_temp, _ = disposable_guard()
    candidate = candidate.resolve(strict=True)
    fixture = Path(tempfile.mkdtemp(prefix="panacea-qt-ready-", dir=runner_temp))
    target = fixture / "Panacea.exe"
    # Keep both files in the runner fixture. Only the new image is launched.
    shutil.copyfile(candidate, target)
    size = candidate.stat().st_size
    with candidate.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    child = None
    launched = 0.0

    def launch(path, token):
        nonlocal child, launched
        launched = time.perf_counter()
        child = subprocess.Popen([str(path), "--panacea-update-ready", token], cwd=fixture,
                                 env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"))
        return child

    try:
        transaction = install_verified(candidate, target, digest, launch)
        if not transaction.success:
            raise RuntimeError(transaction.error)
        while time.perf_counter() - launched < 15:
            if child.poll() is not None:
                raise RuntimeError("The packaged application exited before readiness")
            if verified_upgrade_ready(target, transaction, digest, size, protected=False):
                elapsed = time.perf_counter() - launched
                if elapsed > 15:
                    break
                return {"source_sha": os.environ["PANACEA_TESTED_SHA"], "candidate_sha256": digest,
                        "launch_to_ack_seconds": round(elapsed, 3),
                        "budget_seconds": 15, "path_mode": "portable-fixture"}
            time.sleep(0.05)
        raise TimeoutError("Panacea.exe did not acknowledge startup within 15 seconds")
    finally:
        _kill_only_child(child)


if __name__ == "__main__":
    print(json.dumps(measure(Path(sys.argv[1]))))

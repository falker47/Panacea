"""Historical recovery probe. Run only in a fresh GitHub-hosted Windows VM."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import winreg

from PIL import ImageGrab
from PyInstaller.archive.readers import CArchiveReader

from modules import update_install as install
from modules.updater import verify_file
from scripts.hosted_installer_probe import disposable_guard, run_checked
from scripts.hosted_windows_release_probe import _kill_only_child, launch_visible_legacy
from scripts.packaged_probe import usable_candidate_window

REPO = "falker47/Panacea"
OLD = "e390d2f26f84e108c0e076d834f61927554a77175fe19c22108667f04ec1161f"
NEW = "684121592593afd16042fceab7b6027bf81718aab276fc024ae6d6bf5baf056c"
CONTROL = "abb1b95410c29147686dc4be4acfe3dd5586f74e64cf08de0f1d9bdf5d1f7119"
SETUPS = {"2.0.2": "43568f813848aa75e2cb92c0bc207a8f2e08788e5614910ad19847c008bc81f1",
          "2.1.0": "e60bc29b12b3e4016f891e1e231689b8d82d2c1f6c788a291eb869e1833b9509"}
APP_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{B6C0FB10-27BC-4E6F-9078-40F9E8B49B2D}_is1"


def asset(root, version, name, pin):
    directory = root / version
    directory.mkdir(exist_ok=True)
    path = directory / name
    url = f"https://github.com/{REPO}/releases/download/v{version}/{name}"
    run_checked(["curl.exe", "--fail", "--silent", "--show-error", "--location",
                 "--proto", "=https", "--proto-redir", "=https", "-o", path, url])
    verify_file(path, pin)
    return path


def packaged_client(path, version, pin):
    # Import only hash-pinned published bytecode under its matching Python ABI.
    verify_file(path, pin)
    archive = CArchiveReader(str(path)).open_embedded_archive("PYZ.pyz")
    def embedded(name):
        module = types.ModuleType(f"_probe_{name.replace('.', '_')}")
        sys.modules[module.__name__] = module
        exec(archive.extract(name), module.__dict__)
        return module
    config = embedded("version")
    assert config.VERSION == version and config.GITHUB_REPO.casefold() == REPO.casefold()
    print(f"Frozen {version}: {config.GITHUB_REPO}", flush=True)
    module = embedded("modules.updater")
    return module, module.UpdateClient(config.GITHUB_REPO, config.VERSION)


def registration():
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, APP_KEY, 0, winreg.KEY_READ | view) as key:
                return Path(winreg.QueryValueEx(key, "InstallLocation")[0]), winreg.QueryValueEx(key, "DisplayVersion")[0]
        except FileNotFoundError:
            continue
    return None


def setup(root, version, dest=None):
    path = asset(root, version, "PanaceaSetup.exe", SETUPS[version])
    args = [path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOCLOSEAPPLICATIONS", "/LANG=english"]
    run_checked(args + ([f"/DIR={dest}"] if dest else []))


def helper(root, target, evidence):
    control = asset(root, "2.0.1", "Panacea.exe", CONTROL)
    module, old_client = packaged_client(control, "2.0.1", CONTROL)
    try:
        old_client.check()
    except module.UpdateManifestError as error:
        assert str(error) == "Release page is outside the configured repository.", str(error)
        print(f"2.0.1 differential control: {error}", flush=True)
    else:
        raise AssertionError("2.0.1 did not reproduce the historical error")

    _, client = packaged_client(target, "2.0.2", OLD)
    release = client.check()
    assert release and release.version == "2.1.0", "Historical probe requires releases/latest = v2.1.0"
    print(client.api_url, release.release_url, release.exe_url, release.sha256_url, sep="\n", flush=True)
    assert client.fetch_checksum(release) == NEW
    staged = client.download(release, root)
    verify_file(staged, NEW, release.size)

    # Exercise the unmodified frozen helper entry point with a prepared protected
    # job. GUI confirmation and download callbacks are not injected into the EXE.
    running = launch_visible_legacy(target)
    try:
        time.sleep(4)
        ImageGrab.grab().save(evidence / "legacy-desktop.png")
        workspace = install._create_admin_workspace(target.parent)
        executable = workspace / "Panacea-updater.exe"
        install._copy_verified(target, executable, OLD, protected=True)
        install._copy_verified(staged, workspace / "staged.exe", NEW, protected=True)
        install._write_json(workspace / "job.json", {"target": str(target), "version": release.version},
                            exclusive=True, protected=True)
        process = subprocess.run([str(executable), "--panacea-update-helper", str(workspace)],
                                 cwd=workspace, timeout=150, check=False)
        status = json.loads((workspace / "status.json").read_text(encoding="utf-8"))
        print("Frozen helper:", status, "exit:", process.returncode, flush=True)
        assert process.returncode == 0 and status["status"] == "ready" and running.poll() is None
        verify_file(target, NEW, release.size)
    finally:
        _kill_only_child(running)
    assert usable_candidate_window(target), "Updated Qt window not visible after old app exit"
    assert install.finalize_ready(target, protected=True)
    ImageGrab.grab().save(evidence / "updated-desktop.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["helper", "manual"])
    args = parser.parse_args()
    temp, program_files = disposable_guard()
    if os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted" or registration() is not None:
        raise RuntimeError("Requires a clean GitHub-hosted VM without an existing installation")
    root = Path(tempfile.mkdtemp(prefix="panacea-recovery-", dir=temp))
    dest = program_files / root.name
    assert not dest.exists()
    setup(root, "2.0.2", dest)
    target = dest / "Panacea.exe"
    assert registration() == (dest, "2.0.2")
    verify_file(target, OLD)
    print("Original AppId and installed v2.0.2 payload verified.", flush=True)
    if args.mode == "helper":
        evidence = Path("build/recovery")
        evidence.mkdir(parents=True, exist_ok=True)
        helper(root, target, evidence)
    else:
        # Default upgrade target must be the previous installation for this AppId.
        setup(root, "2.1.0")
        assert registration() == (dest, "2.1.0")
        verify_file(target, NEW)
        print("Official Setup upgraded the same installation and AppId.", flush=True)
    run_checked([target, "--smoke-test"], timeout=90)
    print("Verified fresh packaged Qt startup from the updated path.", flush=True)
    # Leave the unique protected installation and its processes to VM teardown.


if __name__ == "__main__":
    main()

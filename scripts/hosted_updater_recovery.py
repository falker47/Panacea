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

from PIL import Image, ImageGrab
from PyInstaller.archive.readers import CArchiveReader

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


def button_position(frame, reference):
    # Match the rendered English label from the pinned 2.0.2 EXE (100% DPI).
    # Refuse a missing or ambiguous match; never guess based on coordinates.
    def mask(image):
        return image.convert("L").point(lambda value: int(value > 160))
    label = mask(reference)
    screen = mask(frame)
    w, h = label.size
    rows = [label.crop((0, y, w, y + 1)).tobytes() for y in range(h)]
    offset = max(range(h), key=lambda y: sum(rows[y]))
    pixels = screen.tobytes()
    index = -1
    found = []
    while (index := pixels.find(rows[offset], index + 1)) >= 0:
        y, x = divmod(index, screen.width)
        y -= offset
        if 0 <= y <= screen.height - h and x <= screen.width - w:
            if screen.crop((x, y, x + w, y + h)).tobytes() == label.tobytes():
                found.append((x + w // 2, y + h // 2))
    return found[0] if len(found) == 1 else None


def confirm_update(target, evidence):
    from ctypes import POINTER, WinDLL, byref
    from ctypes import wintypes as w
    user = WinDLL("user32", use_last_error=True)

    def api(name, result, *args):
        fn = getattr(user, name)
        fn.argtypes, fn.restype = args, result
        return fn

    window_at = api("WindowFromPoint", w.HWND, w.POINT)
    get_pid = api("GetWindowThreadProcessId", w.DWORD, w.HWND, POINTER(w.DWORD))
    find = api("FindWindowW", w.HWND, w.LPCWSTR, w.LPCWSTR)
    item = api("GetDlgItem", w.HWND, w.HWND, w.INT)
    move = api("SetCursorPos", w.BOOL, w.INT, w.INT)
    mouse = api("mouse_event", None, w.DWORD, w.DWORD, w.DWORD, w.DWORD, w.WPARAM)
    post = api("PostMessageW", w.BOOL, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
    original = usable_candidate_window(target)["pid"]

    def owned(hwnd):
        pid = w.DWORD()
        return hwnd and get_pid(hwnd, byref(pid)) and pid.value == original

    with Image.open(Path(__file__).resolve().parents[1] / "tests/fixtures/v202_install_update.png") as label:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            frame = ImageGrab.grab()
            point = button_position(frame, label)
            if point and owned(window_at(w.POINT(*point))):
                frame.save(evidence / "legacy-desktop.png")
                assert move(*point) and owned(window_at(w.POINT(*point)))
                mouse(2, 0, 0, 0, 0)  # LEFTDOWN / LEFTUP, exclusively on matched text
                mouse(4, 0, 0, 0, 0)
                break
            time.sleep(0.4)
        else:
            frame.save(evidence / "legacy-unmatched.png")
            raise RuntimeError("Install update label was not uniquely visible on the old GUI")
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        dialog = find("#32770", "Install verified update")
        if owned(dialog) and (yes := item(dialog, 6)) and owned(yes):
            ImageGrab.grab().save(evidence / "confirm-desktop.png")
            assert post(yes, 0x00F5, 0, 0)  # BM_CLICK on IDYES in this modal only
            return
        time.sleep(0.2)
    ImageGrab.grab().save(evidence / "confirmation-unmatched.png")
    raise RuntimeError("Expected confirmation dialog did not appear")


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
    running = launch_visible_legacy(target)
    try:
        confirm_update(target, evidence)
        deadline = time.monotonic() + 160
        status = None
        while time.monotonic() < deadline:
            paths = list(target.parent.glob("panacea-update-*/status.json"))
            if paths:
                assert len(paths) == 1, "Unexpected concurrent helper"
                latest = json.loads(paths[0].read_text(encoding="utf-8"))
                if latest != status:
                    print("Frozen helper:", latest, flush=True)
                    status = latest
                if status["status"] == "failed":
                    raise RuntimeError(status["message"])
                if status["status"] == "ready" and running.poll() is not None:
                    break
            time.sleep(0.35)
        else:
            ImageGrab.grab().save(evidence / "upgrade-timeout.png")
            raise RuntimeError(f"Old GUI did not exit after readiness: {status!r}")
        verify_file(target, NEW, release.size)
        assert usable_candidate_window(target), "Updated Qt window not visible after old app exit"
        print("Old GUI closed after confirmed update; installed SHA-256:", NEW, flush=True)
        ImageGrab.grab().save(evidence / "updated-desktop.png")
        _, updated = packaged_client(target, "2.1.0", NEW)
        assert updated.check() is None, "Updated 2.1.0 should no longer offer this update"
    finally:
        _kill_only_child(running)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["helper", "manual", "manual-custom"])
    args = parser.parse_args()
    temp, program_files = disposable_guard()
    if os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted" or registration() is not None:
        raise RuntimeError("Requires a clean GitHub-hosted VM without an existing installation")
    root = Path(tempfile.mkdtemp(prefix="panacea-recovery-", dir=temp))
    dest = program_files / ("Panacea" if args.mode == "manual" else root.name)
    assert not dest.exists()
    setup(root, "2.0.2", None if args.mode == "manual" else dest)
    target = dest / "Panacea.exe"
    assert registration() == (dest, "2.0.2")
    verify_file(target, OLD)
    print("Original AppId and installed v2.0.2 payload verified.", flush=True)
    if args.mode == "helper":
        evidence = Path("build/recovery")
        evidence.mkdir(parents=True, exist_ok=True)
        helper(root, target, evidence)
    else:
        # The installer deliberately uses UsePreviousAppDir=no. A verified custom
        # protected path must be passed explicitly; the default needs no override.
        setup(root, "2.1.0", dest if args.mode == "manual-custom" else None)
        actual = registration()
        assert actual == (dest, "2.1.0"), f"Unexpected installation: {actual!r}"
        verify_file(target, NEW)
        print("Official Setup upgraded the same installation and AppId.", flush=True)
    subprocess.run([str(target), "--smoke-test"], check=True, timeout=90,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Verified fresh packaged Qt startup from the updated path.", flush=True)
    # Leave the unique protected installation and its processes to VM teardown.


if __name__ == "__main__":
    main()

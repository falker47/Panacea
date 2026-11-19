"""Native prepublication probes. Executes only on fresh authorized hosted Windows VMs."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from scripts.build_installer import validate_setup, validate_portable
from scripts.hosted_installer_probe import run_checked
from scripts.release_tools import binary_sha256, write_checksum
from scripts.update_compat.github_emulator import ReleaseFixture
from scripts.update_compat.hosted import candidate_is_current, hosted_guard, published_modules, report
from scripts.update_compat.published import PUBLISHED

APP_ID = "{B6C0FB10-27BC-4E6F-9078-40F9E8B49B2D}_is1"
ARTIFACTS = Path("build/candidate")
SILENT = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOCLOSEAPPLICATIONS"]


def registrations():
    import winreg

    result = []
    root = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
            try:
                key = winreg.OpenKey(hive, root, 0, winreg.KEY_READ | view)
            except FileNotFoundError:
                continue
            with key:
                for index in range(winreg.QueryInfoKey(key)[0]):
                    name = winreg.EnumKey(key, index)
                    with winreg.OpenKey(key, name, 0, winreg.KEY_READ | view) as item:
                        try:
                            display = winreg.QueryValueEx(item, "DisplayName")[0]
                        except FileNotFoundError:
                            display = ""
                        if name.casefold() == APP_ID.casefold() or display.split(" ")[0].casefold() == "panacea":
                            result.append((name, Path(winreg.QueryValueEx(item, "InstallLocation")[0])))
    return result


def assert_registration(dest):
    if registrations() != [(APP_ID, dest)]:
        raise RuntimeError("Expected one Panacea uninstall entry with the original AppId and path")


def build_adapter(tag, meta, rollback):
    work = Path("build/compat-adapter").resolve()
    work.mkdir()
    allowed = {"good": meta["exe_sha256"]}
    if rollback:
        compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        for case, body in [("exit", "return;"), ("timeout", "System.Threading.Thread.Sleep(120000);")]:
            folder = Path("build/compat-faults") / case
            folder.mkdir(parents=True)
            source = folder / "Fault.cs"
            source.write_text("class Fault { static void Main() { " + body + " } }", encoding="ascii")
            exe = folder / "Panacea.exe"
            run_checked([compiler, "/nologo", "/target:winexe", f"/out:{exe}", source])
            write_checksum(exe)
            allowed[case] = binary_sha256(exe)
    spec = work / "fixture.json"
    spec.write_text(json.dumps({"allowed": allowed, "from": tag, "version": meta["version"],
                                "run": os.environ["GITHUB_RUN_ID"], "sha": os.environ["SOURCE_SHA"]}))
    run_checked([sys.executable, "-m", "PyInstaller", "--onefile", "--name", "Panacea-compat-fixture",
                 "--paths", ".", "--specpath", work, "--distpath", work, "--workpath", work / "objects",
                 "--add-data", f"{spec};.", "scripts/update_compat/fixture_helper.py"], timeout=450)
    return work / "Panacea-compat-fixture.exe"


def check_status(case, state, events, exit_code, outcome):
    outcome.update(state)
    states = [event["status"] for event in events]
    expected = ["preparing", "installing"]
    if case == "good":
        if exit_code != 0 or state["status"] != "ready":
            raise RuntimeError(f"Published helper routine failed: {state}")
        expected += ["waiting_ready", "ready"]
    else:
        if exit_code != 1 or state["status"] != "failed":
            raise RuntimeError(f"Fault injection did not reach failed status: {state}")
        if case == "timeout" or "waiting_ready" in states:
            expected.append("waiting_ready")
        expected.append("failed")
        reason = "exited before" if case == "exit" else "in time"
        if reason not in state["message"]:
            raise RuntimeError(f"Unexpected rollback reason: {state}")
    if states != expected:
        raise RuntimeError(f"Unexpected helper state sequence: {events}")
    if case == "good":
        seconds = events[-1]["at"] - events[1]["at"]
        outcome["install_to_ready_seconds"] = seconds
        if not 0 <= seconds <= 15:
            raise RuntimeError("Candidate missed the 15 second readiness budget")


def run_transaction(tag, app, meta, adapter, case, data):
    folder = ARTIFACTS if case == "good" else Path("build/compat-faults") / case
    fixture = ReleaseFixture(ARTIFACTS, "v" + meta["version"], portable_dir=folder)
    with published_modules(app, tag, install=True) as old:
        engine = old["modules.update_install"]
        config = old["version"]
        client = old["modules.updater"].UpdateClient(config.GITHUB_REPO, config.VERSION, opener=fixture.open)
        release = client.check()
        if release is None or release.version != meta["version"]:
            raise RuntimeError("Pinned client did not offer the candidate")
        download = Path("build/compat-download") / case
        staged = client.download(release, download)
        expected = client.fetch_checksum(release)
        workspace = engine._create_admin_workspace(app.parent)
        helper = workspace / "Panacea-updater.exe"
        engine._copy_verified(adapter, helper, binary_sha256(adapter), protected=True)
        engine._copy_verified(staged, workspace / "staged.exe", expected, protected=True)
        engine._write_json(workspace / "job.json", {"target": str(app), "version": release.version},
                           exclusive=True, protected=True)
    outcome = data.setdefault("transactions", {}).setdefault(case, {"requests": fixture.requests})
    helper_log = Path("build/update-compat") / f"helper-{case}.log"
    with helper_log.open("w", encoding="utf-8") as output:
        finished = subprocess.run([str(helper), str(workspace), case], timeout=105, check=False,
                                  stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                  env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"})
    outcome["exit_code"] = finished.returncode
    if not (workspace / "status.json").is_file():
        raise RuntimeError("Fixture helper produced no status: " + str(helper_log))
    state = json.loads((workspace / "status.json").read_bytes())
    events = json.loads((Path("build/update-compat") / f"helper-{case}.json").read_bytes())["events"]
    check_status(case, state, events, finished.returncode, outcome)
    # The published helper retains its own workspace. Account for it before removing fixture files.
    expected_files = {"job.json", "status.json", "staged.exe", "Panacea-updater.exe"}
    if {f.name for f in workspace.iterdir()} != expected_files:
        raise RuntimeError("Unexpected helper workspace contents")
    for name in expected_files:
        (workspace / name).unlink()
    workspace.rmdir()


def candidate_window(app, version):
    # Limit evidence and process cleanup to the exact executable of this test installation.
    command = ("Get-Process -Name Panacea -ErrorAction SilentlyContinue | "
               "Where-Object { $_.Path -eq $env:PANACEA_TEST_PATH -and $_.MainWindowTitle } | "
               "Select-Object Id,MainWindowTitle | ConvertTo-Json -Compress")
    proc = run_checked(["powershell.exe", "-NoProfile", "-Command", command],
                       env={**os.environ, "PANACEA_TEST_PATH": str(app)})
    window = json.loads(proc.stdout or "null")
    if not isinstance(window, dict) or window["MainWindowTitle"] != "Panacea " + version:
        raise RuntimeError(f"Expected a single running candidate reporting {version}: {window}")
    return window


def run(tag, mode, data):
    _, program_files = hosted_guard()
    dest = program_files / "Panacea"
    if dest.exists() or registrations():
        raise RuntimeError("Requires a clean disposable runner with no Panacea installation")
    shortcut = Path(os.environ["ProgramData"]) / "Microsoft/Windows/Start Menu/Programs/Panacea.lnk"
    if shortcut.exists():
        raise RuntimeError("Unexpected pre-existing Panacea shortcut")
    app = dest / "Panacea.exe"
    setup = Path("build/published/PanaceaSetup.exe").resolve(strict=True)
    meta = json.loads((ARTIFACTS / "candidate.json").read_text(encoding="utf-8-sig"))
    _, digest = validate_portable(ARTIFACTS / "Panacea.exe", ARTIFACTS / "Panacea.exe.sha256")
    new_setup = (ARTIFACTS / "PanaceaSetup.exe").resolve(strict=True)
    if (meta["sha"] != os.environ["SOURCE_SHA"] or meta["exe_sha256"] != digest
            or (ARTIFACTS / "PanaceaSetup.exe.sha256").read_text().strip() != validate_setup(new_setup) + "  PanaceaSetup.exe"
            or validate_setup(setup) != PUBLISHED[tag].setup):
        raise RuntimeError("Wrong candidate revision or setup checksum")
    adapter = None if mode == "manual" else build_adapter(tag, meta, mode == "rollback")
    run_checked([setup, *SILENT, "/LANG=italian"])
    assert_registration(dest)
    if binary_sha256(app) != PUBLISHED[tag].exe or not shortcut.is_file():
        raise RuntimeError("Clean installation did not yield the pinned executable and Start Menu shortcut")
    files = {p.name for p in dest.iterdir()}
    language_file = dest / "panacea-language.ini"
    language = language_file.read_bytes()
    if "Language=italian" not in language.decode("utf-8-sig"):
        raise RuntimeError("Expected saved Italian language")
    data.update(source_tag=tag, source_sha256=PUBLISHED[tag].exe, version=meta["version"])
    if mode == "manual":
        run_checked([new_setup, *SILENT])
    else:
        if mode == "rollback":
            for case in ("exit", "timeout"):
                run_transaction(tag, app, meta, adapter, case, data)
                if binary_sha256(app) != PUBLISHED[tag].exe or {p.name for p in dest.iterdir()} != files:
                    raise RuntimeError(f"{case} failed to restore the exact installation")
                run_checked([app, "--smoke-test"], timeout=50)
                data["transactions"][case]["restored_sha256"] = PUBLISHED[tag].exe
        run_transaction(tag, app, meta, adapter, "good", data)
        window = candidate_window(app, meta["version"])
        data["running_window"] = window
        if not candidate_is_current(app, meta, ARTIFACTS):
            raise RuntimeError("Candidate offered a repeated update")
        data["candidate_second_check"] = "up to date"
        # Close the observed Qt window and wait for the one-file bootloader to release the image.
        command = ("$p=Get-Process -Id $env:PANACEA_TEST_PID; "
                   "if ($p.Path -ne $env:PANACEA_TEST_PATH -or !$p.CloseMainWindow()) {throw 'Close failed'}; "
                   "if (!$p.WaitForExit(15000)) {throw 'Candidate did not close'}; "
                   "Get-Process -Name Panacea -ErrorAction SilentlyContinue | "
                   "Where-Object { $_.Path -eq $env:PANACEA_TEST_PATH } | "
                   "ForEach-Object { if (!$_.WaitForExit(15000)) {throw 'Image still in use'} }; exit 0")
        run_checked(["powershell.exe", "-NoProfile", "-Command", command],
                    env={**os.environ, "PANACEA_TEST_PID": str(window["Id"]), "PANACEA_TEST_PATH": str(app)})
    if binary_sha256(app) != digest or language_file.read_bytes() != language or {p.name for p in dest.iterdir()} != files:
        raise RuntimeError("Installed bytes, language or installed file set differ")
    assert_registration(dest)
    data.update(installed_sha256=digest, language_preserved=True, registration=APP_ID)
    uninstallers = list(dest.glob("unins*.exe"))
    if len(uninstallers) != 1:
        raise RuntimeError("Expected one uninstaller")
    run_checked([uninstallers[0], *SILENT])
    deadline = time.monotonic() + 30
    while (dest.exists() or shortcut.exists()) and time.monotonic() < deadline:
        time.sleep(0.2)
    if dest.exists() or shortcut.exists() or registrations():
        raise RuntimeError("Uninstall left files, a shortcut or registration")
    data["uninstalled"] = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tag", choices=PUBLISHED)
    parser.add_argument("mode", choices=("transaction", "rollback", "manual"))
    args = parser.parse_args()
    with report(f"{args.mode}-{args.tag}") as data:
        run(args.tag, args.mode, data)


if __name__ == "__main__":
    main()

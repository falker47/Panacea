# Panacea — Windows maintenance utility

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

Panacea is a Windows desktop utility that groups common maintenance, repair and performance controls behind a Qt Quick / PySide6 interface from 2.1.0. The legacy CustomTkinter 2.0.2 UI remains in source for reference, while the official executable uses Qt Quick. It uses native Windows tools and APIs rather than replacing them with a custom system engine.

The latest published stable version is listed in [GitHub Releases](https://github.com/falker47/Panacea/releases/latest). See the [2.1.1 release notes](docs/releases/2.1.1.md) for Qt updater reliability fixes, the [2.1.0 release notes](docs/releases/2.1.0.md) for the original Qt interface and upgrade procedure, the [2.0.2 release notes](docs/releases/2.0.2.md) for the preceding Tk interface, and the [2.0.1 release notes](docs/releases/2.0.1.md) for earlier changes. CI artifacts and draft releases do not imply stable publication.

The Qt 2.1.0 interface groups features into five primary areas: **Overview**, **Space & Cleanup**, **Diagnostics & Repair**, **Performance & Startup**, and **Guided Maintenance**. The categories below describe capabilities rather than reproducing the navigation labels.

Earlier validation evidence remains available: the [V2 validation report](docs/validation/v2-release-report.md) covers the original seven-section V2.0.0 candidate, while the [functional polish report](docs/validation/v2-polish-report.md) and [Round 2 visual polish report](docs/validation/v2-round2-report.md) document subsequent refinements. These are historical candidate reports, not proof that every operation was tested on the final published version.

## What it does

### Dashboard and monitoring

- Live CPU, RAM and disk usage;
- OS and hardware information;
- Battery information and battery-report generation;
- Windows Update status checks.

### Cleanup

- Removes eligible files from the current user's conventional `%TEMP%` directory and `C:\Windows\Temp`;
- Can clear Chrome, Edge and Firefox cache directories;
- Can empty the Recycle Bin;
- Can open Windows Disk Cleanup;
- Exposes DISM component-store cleanup through the UI.

Locked/in-use files are skipped. Cleanup is irreversible once files or Recycle Bin contents are deleted. Windows restore points do not restore these deleted files.

**Analyze** is optional and read-only: it reports candidates and potential recovery, with an explicit "No files deleted" result. **Clean now** asks for confirmation and checks/deletes eligible files in one traversal, without a required preliminary scan. An earlier analysis never authorizes deletion and filesystem changes can change the result. **View reasons** retains all original skipped/error details; the live output summarizes reasons proven by the backend. Byte totals describe the logical size of eligible/deleted files, not a measured drive free-space delta.

**Quick cleanup** asks for one explicit confirmation covering three automatic operations, executed in order:

1. Delete eligible temporary files from validated locations.
2. Empty the entire Recycle Bin.
3. Run `DISM /Online /Cleanup-Image /StartComponentCleanup` to remove superseded Windows components.

After all three steps have returned, and provided no cancellation, shutdown request or unknown command completion prevents it, Panacea opens Windows Disk Cleanup. That fourth action only launches the native utility: the user must select and confirm any additional cleaning inside Windows.

Quick cleanup reports partial results and failures. Cancellation is honored between steps, not by forcibly terminating a running Windows command. DISM may take time or require a restart.

Windows Disk Cleanup's standalone **Open utility** action also only opens the external Windows tool.

Cleanup, optimization, command and Resurrection output opens at an accepted explicit start and remains available after completion and navigation. Closing a panel during execution is respected until the next explicit operation.

Cleanup accepts the conventional local-user Temp and explicit browser cache roots, verifies opened Windows objects and refuses junctions, hardlinks and unverifiable paths. Protected cleanup and Turbo snapshot storage require native identity/case-sensitivity support (Windows 10 version 1803 or newer, or Windows 11); unsupported filesystems and queries fail closed. Redirected or unconventional user storage may require using Windows' own tools.

### Disk optimization

- Enumerates local fixed drives and their capacity/availability;
- Runs Windows `defrag <drive> /O`, which lets Windows choose the appropriate optimization for the media;
- Can open the native **Defragment and Optimize Drives** interface.

### Repair and network tools

Panacea exposes commands including:

- `sfc /scannow`;
- `DISM /Online /Cleanup-Image /CheckHealth`;
- `DISM /Online /Cleanup-Image /RestoreHealth`;
- `ipconfig /flushdns`;
- `netsh winsock reset`;
- `chkdsk <Windows drive>: /scan /perf` inside the multi-step maintenance protocol.

The command runner uses an explicit set of permitted commands rather than executing arbitrary user-supplied shell instructions. Results, failures and restart requirements are reported through the interface.

### Restore points

Panacea requests a restore point through PowerShell and verifies a newer sequence with the unique description of this exact request. System Restore is not enabled implicitly. Unknown, unchanged or failed verification is reported as failure; Windows may throttle creation.

Enable protection explicitly through Windows before using Resurrection if it is disabled.

A restore point is a prerequisite for Guided Maintenance, not a backup of personal files and not a way to reverse permanent deletion.

### Turbo Mode

Turbo Mode can change:

- The active Windows power plan;
- The current user's `VisualFXSetting` registry preference (immediate animation changes are not claimed);
- The running state of `SysMain`, `WSearch` and `Spooler`.

The controls save the original power scheme, service running state and visual preference before changing them. Turning a control off restores that saved value; failures and unavailable state remain explicit. Windows policies and external changes can still prevent restoration.

### System Resurrection / Guided Maintenance

The automated protocol currently executes ten steps in order:

1. Create and verify a new Windows restore point.
2. Clean supported browser caches.
3. Remove eligible temporary files.
4. Empty the Recycle Bin.
5. Flush the DNS cache using `ipconfig /flushdns`.
6. Reset Winsock using `netsh winsock reset`.
7. Optimize the Windows system drive using `defrag /O`.
8. Run an online CHKDSK scan.
9. Check Windows component-image health using DISM.
10. Scan protected system files using SFC.

The verified restore point is mandatory: if its creation cannot be verified, the sequence stops before cleanup.

Each step has an individual result. A noncritical failure can produce a partial outcome without automatically stopping every subsequent step. If command completion becomes unknown, the sequence stops and the maintenance guard can block further operations until the state is safely verifiable, potentially requiring a Windows restart.

The panel retains individual step results and its completed, partial, failed or cancelled summary. Progress advances when a step finishes. Cancellation stops before the next step; it does not forcibly terminate the current Windows command.

Browser caches, temporary files and Recycle Bin deletion are irreversible and explicitly confirmed before starting the sequence. Network reset may interrupt connections or require a restart. Save open work first.

## Permissions and safety model

Panacea requests Administrator privileges at normal startup because several supported operations require elevation. Declining or failing elevation prevents normal application startup. The dedicated packaged GUI smoke-test mode is an exception and does not perform maintenance or request elevation.

Using native Windows commands does **not** make every operation risk-free. Before running cleanup, service changes, repair commands or the automated protocol:

- Save open work;
- Keep a current backup of important data;
- Understand that cache/temp/Recycle Bin deletion is irreversible;
- Expect network reset operations to require a restart in some cases;
- Avoid stopping services you actively depend on (for example Print Spooler while printing);
- Do not treat a restore point as a replacement for a personal-file backup.

The project does not implement a registry cleaner or automatic driver updater. It **does** write one documented visual-effects registry setting and can stop/start selected Windows services.

Do not disable Windows security protections to install or run Panacea.

## Installer and future updates

**Recommended installation:** Windows 10 version 1803 or newer, or Windows 11, on an x64-compatible system. The installed edition uses Inno Setup and requires Administrator privileges.

Download `PanaceaSetup.exe` and its matching `PanaceaSetup.exe.sha256` from the [official stable release](https://github.com/falker47/Panacea/releases/latest).

Before running Setup, verify the downloaded installer against its separately published SHA-256 manifest. From PowerShell in the download directory:

```powershell
Get-FileHash .\PanaceaSetup.exe -Algorithm SHA256
```

Compare the reported hash with the 64-character hexadecimal digest in `PanaceaSetup.exe.sha256`, ignoring letter case. Do not execute the installer if the values differ.

The installer installs Panacea as an administrator-protected per-machine application in `Program Files\Panacea`. Inno Setup registers the Windows uninstaller and creates a Start Menu shortcut, with a desktop shortcut optionally available.

The published Windows binaries are not Authenticode-signed. SHA-256 verification checks integrity against the published manifest; it does not establish a cryptographically signed publisher identity. GitHub release provenance remains part of the trust boundary.

The installer does not touch existing portable V1 executables. Older v1.47 users should close the app and install V2 manually, not use the unverified legacy in-app Install banner.

The corrected updater offers checksum-verified, user-confirmed in-place updates for protected installations. Installed Panacea 2.0.2 can offer the published Qt 2.1.0 as an update; the original protected executable remains recoverable until the new Qt UI acknowledges startup. Installed 2.0.0/2.0.1 should upgrade with Setup because those older binaries may reject canonical GitHub release URLs on case-sensitive checks.

Desktop/Downloads copies deliberately cannot perform elevated in-place replacement. Portable copies remain supported through manual updates: download `Panacea.exe` and its matching `Panacea.exe.sha256` from the official release, verify the checksum, close the application and replace the portable executable.

The existing ZEROfilez stable `Panacea.exe` link remains supported.

Installation does not mean automatic silent background update. The runtime asks for approval and must satisfy protected-file and directory checks.

## Updates

The desktop app checks GitHub Releases in the background and offers a manual check. It selects exactly `Panacea.exe` and `Panacea.exe.sha256`, rejects downgrade and unofficial URLs, and verifies the downloaded size, SHA-256 and Windows executable header before installation.

Automatic installation preserves the previous binary until the new GUI acknowledges readiness and rolls back on replacement or launch failure. Elevated replacement requires a protected installation directory; portable copies in user-writable Desktop or Downloads directories use the release-page/manual download alternative. Source execution never replaces the Python interpreter. GitHub release provenance remains part of the trust boundary; checksum verification is not Authenticode signing.

## Privacy and local logs

Panacea does not require a separate application account for normal use.

At startup, the application attempts to create a local log at:

```text
%USERPROFILE%\Documents\SystemOptimizer\log.txt
```

Logging failures do not prevent startup. The log can contain operation details, diagnostic messages, file paths and error information. Treat it as potentially sensitive local data. It can be reviewed or removed manually after closing the application.

Panacea makes HTTPS requests to the GitHub Releases API to check for updates. Downloading and installing an offered update requires explicit approval. Network interactions with GitHub and the behavior of native Windows utilities are subject to those external systems.

The local log and update checks are separate mechanisms; an update check is not an upload of the local maintenance log.

## Run from source

Requirements:

- Windows 10 or 11 (Windows 10 version 1803 or newer is required for the protected cleanup and snapshot functionality described above);
- Python 3.10+;
- Administrator privileges for normal application execution and supported maintenance operations.

```powershell
git clone https://github.com/falker47/Panacea.git
cd Panacea
python -m pip install -r requirements.txt
python qt_app/main.py
```

The original CustomTkinter UI is still accessible in source with `python main.py` for reference; the official frozen `Panacea.exe` is built from `qt_app/main.py`.

Normal startup requests Windows elevation when necessary. Source execution is intended for development and does not install the application or enable automatic replacement of the Python interpreter.

## Build the executable

```cmd
scripts\build_exe.bat
```

The Qt single-file executable is written to `dist\Panacea.exe`, with `dist\Panacea.exe.sha256` and Windows version metadata derived from `version.py`. The build uses the checked-in `Panacea.spec` and pinned dependencies.

New build outputs under `dist/` are ignored by Git. However, the repository still contains a previously tracked `dist/Panacea.exe`. That repository copy is not identical to the published v2.0.2 release asset and must not be treated as the current distributable binary.

**Download published binaries from GitHub Releases, not from the repository's `dist/` directory.**

For an automated local build use `python scripts/build.py`. `Panacea.exe --smoke-test` opens and closes the GUI without maintenance or UAC elevation.

The installer build uses `python scripts/build_installer.py` and requires Inno Setup 6 at build time.

## Verification

The repository CI includes fixture-based unit/integration tests, Ruff static checks, compilation and import smoke, performance and UI probes, Windows executable and installer builds, PE/version verification, and a safe packaged GUI smoke test.

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
python -m ruff check .
```

The ordinary test suite uses controlled fixtures and mocks rather than performing destructive maintenance on the user's computer.

Separate GitHub Actions integration jobs can exercise scoped native cleanup, installer operations, updating, rollback and uninstall on disposable Windows runners. These jobs run for qualifying same-repository pull requests and trusted main-branch pushes. Publishing v2.1.0 requires all three Windows CI jobs (GUI, isolated filesystem/update, protected installer/rollback) to succeed on the exact main commit. A skipped or pending job is not proof of validation.

The **Prepare Windows release** workflow accepts an immutable reviewed commit SHA and an exact tag matching `version.py`. It executes its checks and attaches `Panacea.exe`, `PanaceaSetup.exe` and their checksums to a **draft** GitHub Release.

Stable publication of Qt 2.1.0 is gated on the reviewed main commit and the three successful native Windows CI jobs, with independently verified release-asset SHA-256 digests. See the [2.1.0 release notes](docs/releases/2.1.0.md) and [validation evidence](docs/validation).

CI success, packaged smoke tests and disposable-runner results are not substitutes for manual testing of elevated Windows maintenance operations, real-world updates, interruption recovery and rollback on representative Windows 10/11 systems.

Check each run, job, event and source commit individually; missing, skipped or pending checks are not evidence of successful execution.

## Repository map

```text
.
├── main.py
├── panacea_ui.py
├── version.py
├── modules/
│   ├── cleanup.py
│   ├── commands.py
│   ├── disk.py
│   ├── performance.py
│   ├── quick_cleanup.py
│   ├── restore.py
│   ├── system_monitor.py
│   ├── update_install.py
│   ├── updater.py
│   └── ...
├── packaging/
│   └── Panacea.iss
├── assets/
├── docs/
├── scripts/
│   ├── build.py
│   ├── build_exe.bat
│   └── build_installer.py
├── tests/
├── Panacea.spec
├── requirements.txt
└── requirements-dev.txt
```

## License status

No project-wide license file is currently present in this repository. The previous README displayed an MIT badge without a corresponding `LICENSE`; that unsupported claim has been removed.

Third-party components may have their own licenses, including the Lucide icon assets under `assets/icons/lucide/`. Those notices do not establish a project-wide license for Panacea.

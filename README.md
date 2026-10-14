# Panacea — Windows maintenance utility

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

Panacea is a Windows desktop utility that groups common maintenance, repair and performance controls behind a CustomTkinter interface. It uses native Windows tools and APIs rather than replacing them with a custom system engine.

The current codebase is the **2.0.0 release candidate**. Public releases remain authoritative; a local candidate or CI artifact does not imply stable publication.

See the [V2 validation report](docs/validation/v2-release-report.md) for the seven-section redesign, audits, screenshots, candidate checksum and outstanding release gates.
The [functional polish report](docs/validation/v2-polish-report.md) records optional analysis, direct cleanup and visible operation output.
The [Round 2 visual polish report](docs/validation/v2-round2-report.md) records the latest candidate, tighter Dashboard spacing, focused Resurrection layout and updated sidebar footer.

## What it does

### Dashboard and monitoring
- live CPU, RAM and disk usage;
- OS and hardware information;
- battery information and battery-report generation;
- Windows Update status checks.

### Cleanup
- removes files from the current user's `%TEMP%` directory and `C:\Windows\Temp`;
- can clear Chrome, Edge and Firefox cache directories;
- can empty the Recycle Bin;
- can open Windows Disk Cleanup;
- exposes DISM component-store cleanup through the UI.

Locked/in-use files are skipped. Cleanup is irreversible once files or Recycle Bin contents are deleted.

**Analyze** is optional and read-only: it reports candidates and potential recovery,
with an explicit “No files deleted” result. **Clean now** asks for confirmation and
checks/deletes eligible files in one traversal, without a required preliminary
scan. An earlier analysis never authorizes deletion and filesystem changes can
change the result. **View reasons** retains all original skipped/error details;
the live output summarizes reasons proven by the backend. Byte totals describe
the logical size of eligible/deleted files, not a measured drive free-space delta.
Windows Disk Cleanup's **Open utility** only opens the external Windows tool.

Cleanup, optimization, command and Resurrection output opens at an accepted
explicit start and remains available after completion and navigation. Closing a
panel during execution is respected until the next explicit operation.

Cleanup accepts the conventional local-user Temp and explicit browser cache roots, verifies opened Windows objects and refuses junctions, hardlinks and unverifiable paths. Protected cleanup and Turbo snapshot storage require native identity/case-sensitivity support (Windows 10 version 1803 or newer, or Windows 11); unsupported filesystems and queries fail closed. Redirected or unconventional user storage may require using Windows' own tools.

### Disk optimization
- enumerates local fixed drives and their capacity/availability;
- runs Windows `defrag <drive> /O`, which lets Windows choose the appropriate optimization for the media;
- can open the native **Defragment and Optimize Drives** interface.

### Repair and network tools
Panacea exposes commands including:
- `sfc /scannow`;
- `DISM /Online /Cleanup-Image /CheckHealth`;
- `DISM /Online /Cleanup-Image /RestoreHealth`;
- `ipconfig /flushdns`;
- `netsh winsock reset`;
- `chkdsk <Windows drive>: /scan /perf` inside the multi-step maintenance protocol.

### Restore points
Panacea requests a restore point through PowerShell and verifies a newer sequence with the unique description of this exact request. System Restore is not enabled implicitly. Unknown, unchanged or failed verification is reported as failure; Windows may throttle creation. Enable protection explicitly through Windows before using Resurrection if it is disabled.

### Turbo Mode
Turbo Mode can change:
- the active Windows power plan;
- the current user's `VisualFXSetting` registry preference (immediate animation changes are not claimed);
- the running state of `SysMain`, `WSearch` and `Spooler`.

The controls save the original power scheme, service running state and visual preference before changing them. Turning a control off restores that saved value; failures and unavailable state remain explicit. Windows policies and external changes can still prevent restoration.

### System Resurrection protocol
The automated protocol currently sequences:
1. verified restore point (the sequence stops if this prerequisite fails);
2. browser-cache cleanup;
3. temp-file and Recycle Bin cleanup;
4. DNS/Winsock reset;
5. `defrag /O` on the Windows system drive;
6. online CHKDSK scan;
7. DISM health check;
8. SFC scan.

The panel retains individual step results and its completed, partial, failed or cancelled summary. Progress advances when a step finishes; cancellation stops before the next command. Browser caches, temporary files and Recycle Bin deletion are irreversible and confirmed before starting.

## Permissions and safety model

Panacea requests Administrator privileges at startup because several supported operations require elevation.

Using native Windows commands does **not** make every operation risk-free. Before running cleanup, service changes, repair commands or the automated protocol:

- save open work;
- keep a current backup of important data;
- understand that cache/temp/Recycling Bin deletion is irreversible;
- expect network reset operations to require a restart in some cases;
- avoid stopping services you actively depend on (for example Print Spooler while printing).

The project does not implement a registry cleaner or automatic driver updater. It **does** write one documented visual-effects registry setting and can stop/start selected Windows services.

## Installer and future updates

Download the recommended `PanaceaSetup.exe` plus its separately published SHA-256
manifest to install Panacea as an administrator-protected per-machine application
in `Program Files\Panacea`. Inno Setup registers the Windows uninstaller and
creates a Start Menu shortcut, with a desktop shortcut optionally available.

The installer does not touch existing portable V1 executables. Older v1.47
users should close the app and install V2 manually, not use the unverified
legacy in-app Install banner.

The V2 updater can offer checksum-verified, user-confirmed in-place updates
for this protected installation. Desktop/Downloads copies deliberately cannot
perform elevated in-place replacement; portable copies stay supported with
manual updates and keep the existing ZEROfilez stable `Panacea.exe` link.

Installation does not mean automatic silent background update. The runtime
asks for approval and must satisfy protected-file and directory checks.

## Updates

The desktop app checks GitHub Releases in the background and offers a manual check. It selects exactly `Panacea.exe` and `Panacea.exe.sha256`, rejects downgrade and unofficial URLs, and verifies the downloaded size, SHA-256 and Windows executable header before installation.

Automatic installation preserves the previous binary until the new GUI acknowledges readiness and rolls back on replacement or launch failure. Elevated replacement requires a protected installation directory; portable copies in user-writable Desktop or Downloads directories use the release-page/manual download alternative. Source execution never replaces the Python interpreter. GitHub release provenance remains part of the trust boundary; checksum verification is not Authenticode signing.

## Run from source

Requirements:
- Windows 10 or 11;
- Python 3.10+.

```powershell
git clone https://github.com/falker47/Panacea.git
cd Panacea
python -m pip install -r requirements.txt
python main.py
```

## Build the executable

```cmd
scripts\build_exe.bat
```

The generated executable is written to `dist\Panacea.exe`, with `dist\Panacea.exe.sha256` and Windows version metadata derived from `version.py`. The build uses the checked-in `Panacea.spec` and pinned dependencies. Build outputs are not committed; distributable binaries belong in GitHub Releases.

For an automated local build use `python scripts/build.py`. `Panacea.exe --smoke-test` opens and closes the GUI without maintenance or UAC elevation.

## Verification

The repository CI runs fixture-based unit/integration tests, static checks, compilation and import smoke, builds the Windows executable, verifies its PE header and version, and runs a safe packaged GUI smoke. Tests do not clean host files, change services or power plans, or run system repairs.

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
python -m ruff check .
```

The **Prepare Windows release** workflow accepts an immutable reviewed commit SHA and an exact tag matching `version.py`. It executes the checks and attaches `Panacea.exe` plus its checksum to a **draft** GitHub Release. Stable publication is a separate human approval gate after real Windows, prior-version update/restart, rollback and security checks. See [release notes](docs/releases/2.0.0.md) and [validation evidence](docs/validation).

This is a build/smoke gate, not a substitute for manual testing of elevated Windows maintenance operations on representative Windows 10/11 systems.

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
│   ├── restore.py
│   └── system_monitor.py
├── assets/
├── docs/
├── scripts/
│   └── build_exe.bat
└── requirements.txt
```

## License status

No project-wide license file is currently present in this repository. The previous README displayed an MIT badge without a corresponding `LICENSE`; that unsupported claim has been removed.

# Panacea — Windows maintenance utility

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

Panacea is a Windows desktop utility that groups common maintenance, repair and performance controls behind a CustomTkinter interface. It uses native Windows tools and APIs rather than replacing them with a custom system engine.

The current codebase is **v1.48**.

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

### Disk optimization
- enumerates available drive letters;
- runs Windows `defrag <drive> /O`, which lets Windows choose the appropriate optimization for the media;
- can open the native **Defragment and Optimize Drives** interface.

### Repair and network tools
Panacea exposes commands including:
- `sfc /scannow`;
- `DISM /Online /Cleanup-Image /CheckHealth`;
- `DISM /Online /Cleanup-Image /RestoreHealth`;
- `ipconfig /flushdns`;
- `netsh winsock reset`;
- `chkdsk C: /scan /perf` inside the multi-step maintenance protocol.

### Restore points
Panacea can enable System Restore and request a restore point through PowerShell. Windows may throttle restore-point creation; the current implementation detects the common case where `Checkpoint-Computer` exits successfully without creating a new point.

### Turbo Mode
Turbo Mode can change:
- the active Windows power plan;
- the current user's `VisualFXSetting` registry value;
- the running state of `SysMain`, `WSearch` and `Spooler`.

These are real system changes, not just UI preferences. The controls also provide the corresponding restore path, but the app cannot guarantee that every machine or policy configuration will return to an identical prior state.

### System Resurrection protocol
The automated protocol currently sequences:
1. restore-point attempt;
2. browser-cache cleanup;
3. temp-file and Recycle Bin cleanup;
4. DNS/Winsock reset;
5. `defrag /O` on `C:`;
6. online CHKDSK scan;
7. DISM health check;
8. SFC scan.

It is intentionally explicit here because this workflow modifies or cleans several parts of the system in one run.

## Permissions and safety model

Panacea requests Administrator privileges at startup because several supported operations require elevation.

Using native Windows commands does **not** make every operation risk-free. Before running cleanup, service changes, repair commands or the automated protocol:

- save open work;
- keep a current backup of important data;
- understand that cache/temp/Recycling Bin deletion is irreversible;
- expect network reset operations to require a restart in some cases;
- avoid stopping services you actively depend on (for example Print Spooler while printing).

The project does not implement a registry cleaner or automatic driver updater. It **does** write one documented visual-effects registry setting and can stop/start selected Windows services.

## Updates

The desktop app checks this repository's GitHub Releases for a newer version. For packaged builds it can download a release `.exe` and replace the current executable.

The current updater relies on HTTPS/GitHub release delivery but does **not** verify a separately published signature or release checksum before replacement. Treat release provenance as part of the trust boundary.

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

The generated executable is written to `dist\Panacea.exe`. Build outputs are not intended to be committed to the source tree; distributable binaries should be published through GitHub Releases.

## Verification

The repository CI runs on Windows and:
- compiles the Python sources;
- imports the main UI modules;
- verifies the declared application version;
- builds the PyInstaller executable;
- checks that `dist\Panacea.exe` was produced.

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
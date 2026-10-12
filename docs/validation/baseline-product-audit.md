# Baseline and capability audit — 12 October 2026

## Source and remote state

The clean local checkout initially had main at 05c58097a6e93b17daca9dc60bfa6ed7392d8881, with VERSION 1.47 despite its last commit's 1.48 title. Live main was d605d5c8f135b49ca20c75b85845bf216b648ef0, VERSION 1.48. Work branch codex/panacea-next-generation was created from that live main; main is preserved. No applicable AGENTS.md was found in the repository or its parent chain, and no open Panacea PR was returned by the GitHub connector.

Live current-main CI was successful: https://github.com/falker47/Panacea/actions/runs/37127575525. The public latest release was v1.47, asset Panacea.exe, 22,290,919 bytes, GitHub-reported SHA-256 67319fdeca35ba0e8e7cd36031c7098d42f3d535a8598935bd865c03fe77aab9. This metadata read is not an independently downloaded-file verification.

The operational Trello card was read at https://trello.com/c/gboBbkqy. No messages, comments or status changes were sent to Trello.

## Capabilities actually checked

Available: Windows 11 build 26300; Python 3.14.3; CustomTkinter 5.2.2; Pillow 12.1.1; packaging 26.0; PyInstaller 6.19.0; pytest 9.0.2; ruff 0.11.12; Git and connected GitHub/Trello read tools; native Windows Computer Use via @oai/sky; read-only hardware queries outside the sandbox; ctypes and temporary NTFS fixtures for native API tests. A real @oai/sky dashboard screenshot was captured and retained. Repository GUI probes render the app's own views without invoking maintenance.

No additional tools were installed. define-goal and product-design were optional and unnecessary: the goal tools and explicit user design brief are available. No Authenticode certificate or disposable Windows VM has been supplied. The sandbox denies Git metadata writes and CIM queries; authorized Git operations and read-only GUI/CIM measurements used reviewed escalations. Native Windows Computer Use initialized successfully; a later input attempt failed with 'foreground window did not report a process id', so screenshots of all views were additionally collected by the app's own read-only render harness.

## Existing flows and host effects

Later bootstrap correction: the installed global PyInstaller6.19 was not used for the final candidate. Official PyPI dependencies were installed into build/release-venv with PyInstaller6.22.3, without updating global Python packages. The build rejects an older toolchain; see final-security.md and candidate-package.json. No new agent plugin was needed.

| Section | Existing flow | Host impact and required feedback |
| --- | --- | --- |
| Dashboard | CPU/RAM/disk graphs, OS/uptime/hardware, Windows Update query, battery report, app update check | Mostly read-only; Windows Update installation/restart and executable replacement require explicit actions |
| Cleanup | Temp files, Recycle Bin, cleanmgr, DISM component cleanup | File deletion is irreversible; preview, contextual confirmation, skipped/error counts and constrained roots |
| Disk | Enumerate drives, defrag /O, Windows Optimize GUI | Real disk optimization; validate drive, confirm, report return status |
| Tools | SFC, DISM health scans/repair, CHKDSK, DNS flush/Winsock reset, restore point and battery report | Long commands must not block UI; network reset may require restart; restore point must be verified |
| Apps | Open installed programs, startup settings and Task Manager | Launch existing Windows interfaces; no automatic uninstall |
| Turbo | Power scheme, visual setting, SysMain, Search, Spooler, master toggle | Persist exact originals before changing them; unknown state stays unknown; loss of indexing/printing and battery tradeoffs must be visible |
| Resurrection | Restore, browser/temp/bin cleanup, network reset, disk optimization, CHKDSK, DISM, SFC | Stop if restore safety prerequisite fails; per-step result, completed-step progress, persistent partial/failed/cancelled status |

## Observed baseline problems

- Every sidebar item uses a different saturated background; active selection has no distinct state.
- 900x560 startup layout is cramped, particularly lower graph cards and longer operational descriptions.
- Green terminal logs, gold Resurrection framing and a large master control compete with useful content.
- CPU/RAM labels wait for sequential slow hardware lookups; initial valid metric median was 3.305 seconds across five fresh source processes.
- TEMP and browser traversal did not pin Windows reparse ancestors; directory deletion bypassed accurate counts.
- Commands used shell fragments, even where Popen received a list containing cmd /c.
- Turbo restored defaults, losing custom original power/service/visual state.
- Restore verification treated some unqueryable sequences as success and enabled protection implicitly.
- Resurrection advanced progress before completion, ignored several command failures and overwrote its final status with Ready.
- Updater picked the first .exe, lacked independent checksum verification, replaced the running binary and removed backups without readiness acknowledgment.
- Workers invoked Tk.after directly; deferred exception lambdas referenced cleared exception variables. Shutdown and repeated operations needed a shared lifecycle contract.
- CI hardcoded VERSION == '1.48', performed no behavior tests and produced no release/checksum pipeline.

## Baseline evidence and limits

Compile and import smoke succeeded on live-main source. The repository had no behavior-test suite. Screenshots of all seven views are in screenshots/before; @oai/sky capture is before-dashboard.png. Five real CIM samples are in baseline-performance.json; five fresh source startup/heartbeat samples are in before-startup.json. Direct PanaceaApp readiness excludes main.py's forced one-second splash, UAC, cold OS cache and PyInstaller extraction. Do not label these measurements as full executable cold startup.

ZEROfilez source confirms Panacea in its pc-programs catalog and shared Essentials taxonomy. js/data.js retains name, ICONS.panacea and https://github.com/falker47/Panacea/releases/latest/download/Panacea.exe. The setup and PC catalog share their category taxonomy. The deployed site is https://falker47.github.io/ZEROfilez/; web-tool access failed during this initial probe. Deployed UI and new latest download remain distribution gates; source correctness is not a substitute for them.

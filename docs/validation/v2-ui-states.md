# V2 native UI state captures

Run: 2026-10-13. **13/13 fixture captures passed**, with zero recorded Tk callback or UI-dispatch errors. Every saved PNG was visually inspected. These are screenshots of the real native CustomTkinter application with inert, explicitly synthetic backend results. Every image displays **SIMULATED RESULTS · UI fixture only** in the update bar.

## Reproduction and evidence

```powershell
.\build\release-venv\Scripts\python.exe scripts/ui_state_check.py
```

The command exited 0. The script launches one child process per case, asserts the relevant model/control/status values, waits for rendering, captures the native client area, and closes the window. No capture GUI remains open. `--list` lists the cases without launching a window; `--case NAME` selects a single fixture. The script passed Python compilation and Ruff checks.

- [Capture script](../../scripts/ui_state_check.py)
- [Machine-readable manifest](screenshots/v2-states/manifest.json), including all assertions' observed values, per-case timestamps, source and PNG SHA-256 hashes, child exit status, stdout/stderr, and callback errors.
- Each screenshot has an adjacent JSON record containing its observed state and capture metadata.
- All captures: 1366 × 768 client pixels, CTk widget scale 1.0, window scale 1.0, reported native window DPI 96, screen 2560 × 1440. Windows scaling was not changed.
- All captures used the same `panacea_ui.py` SHA-256: `5b33cfc755e1d087ab8f5a6ad780c149065fdabfe24076dc857b5d2fdbf83554`.
- Captured script SHA-256: `c6d86aac9d403c521a18dedada7d50fc9acf8d7e1016eead8c22da4edd25194b`. A later harness-only change substitutes an inert `MaintenanceGuard` before application initialization, preserving isolation after the new guard integration. The saved screenshots/manifests remain evidence of the recorded capture revision; no new GUI capture was performed for that harness update.

## State coverage

| Screenshot | Synthetic input and checked outcome |
| --- | --- |
| [Cleanup loading](screenshots/v2-states/cleanup-loading.png) | A held preview worker shows Scanning and Running; deletion is disabled while it remains busy. |
| [Cleanup success](screenshots/v2-states/cleanup-success.png) | Preview returns 24 files / 3.0 MB, Completed; deletion control is enabled after the worker completes. No file is deleted. |
| [Cleanup partial](screenshots/v2-states/cleanup-partial.png) | Preview returns the same counts with one skipped entry and one error; both counts and Partial are visible. |
| [Cleanup error](screenshots/v2-states/cleanup-error.png) | Preview raises a synthetic PermissionError; failed preview, Failed operation status, and error toast are visible. |
| [Disk unavailable](screenshots/v2-states/disk-unavailable.png) | A synthetic offline Z: volume is unavailable; optimization is disabled. |
| [Turbo unknown](screenshots/v2-states/turbo-unknown.png) | All live settings and saved-original availability are unknown. The master and setting switches are disabled; saved originals show unavailable and restoration is disabled. Refresh remains available. |
| [Turbo saved partial](screenshots/v2-states/turbo-saved-partial.png) | High performance is on; Pause SysMain and Pause Print Spooler switches are off; Visual and Search states are unknown. Two saved originals are reported. Master remains Unknown/disabled while Restore saved settings is enabled independently. |
| [Resurrection running](screenshots/v2-states/resurrection-running.png) | Restore point and Browser caches have completed; Temporary files is held running; seven later steps remain pending. Progress is 2/10. |
| [Resurrection completed](screenshots/v2-states/resurrection-completed.png) | All ten synthetic phases succeed. All phase labels show Completed; progress and summary show 10/10 finished. |
| [Resurrection partial](screenshots/v2-states/resurrection-partial.png) | Network reset fails synthetically; all ten phases are attempted, nine complete, one fails. Summary is Partial and progress is 10/10 finished. Full progress does not imply ten successes. |
| [Resurrection failed](screenshots/v2-states/resurrection-failed.png) | Restore point creation returns false. Exactly one phase is attempted and fails; the remaining nine are Not run. Progress is 1/10, status Failed. |
| [Resurrection cancelled](screenshots/v2-states/resurrection-cancelled.png) | Cancellation is requested after Browser caches. Exactly two phases complete; eight remain Not run. Progress is 2/10, status Cancelled. |
| [Dashboard unavailable](screenshots/v2-states/dashboard-unavailable.png) | CPU, memory and disk samples are unavailable. CPU and RAM percentage show an em dash, disk shows Unavailable, and Windows Update shows the synthetic unavailable result. |

The Resurrection fixture runs the real worker/controller and sequence with configured inert backend methods. The displayed phase names remain the product's real names: Restore point, Browser caches, Temporary files, Recycle Bin, DNS cache, Network reset, Optimize drive, Disk scan, Image health, and System files. Cleanup likewise runs the real preview worker/controller. Disk, Turbo and Dashboard use the real presentation methods with explicit synthetic inputs.

## Isolation and limitations

Before application initialization, the script replaces Logger and every backend manager with inert objects and suppresses all startup metrics, metadata, disk, Turbo and update queries. Unconfigured backend access raises an assertion. Process launch, shell/file launch, browser opening and confirmation APIs are blocked in each capture child. These fixtures performed no maintenance, deletion, service/registry/power changes, live update request, or executable replacement. Fixture error text and fabricated file counts are evidence of UI behavior only.

This supplements the separate full-section layout matrix. It covers representative states at one viewport and scale; it does not establish all combinations of screen size, true Windows DPI, keyboard navigation, actual administrator behavior, real backend execution, packaged-EXE behavior, or performance. Confirmation dialogs are bypassed by the fixture harness, so their behavior is not established here. The running-state workers are released only during fixture teardown; their eventual operation result is outside those captures.

Each child reported CustomTkinter's inability to load its preferred `font_shapes` font and use of the `circle_shapes` fallback. The warning is preserved in the manifest, and the reviewed screenshots remain legible. These images therefore document rendering with that fallback, not successful loading of the preferred shape font.

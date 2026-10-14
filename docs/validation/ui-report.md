# Desktop UI, workers and monitor validation

Date: 2026-10-12. Candidate: 1.49.0. Domain owner: desktop_ui.

## Implemented

- Preserved all seven sections: Dashboard, Cleanup, Disk, Tools, Apps, Turbo and Resurrection. Shared Segoe UI typography, restrained dark surfaces and a blue accent replace the previous bright section colors and oversized Resurrection hero.
- Active sidebar state, Ctrl+1 through Ctrl+7 navigation, keyboard button activation/focus borders, compact action cards, readable Consolas logs and dashboard shortcuts are implemented.
- Noninitial sections build once on first navigation. Font objects are reused. This change followed the controller's measured constructor regression in the first redesign; final timing measurements are controller-owned and no unmeasured startup improvement is claimed here.
- Charts redraw on canvas resize. Dashboard, Tools, Apps and Turbo have scrollable content; narrow/scaled heights retain access to content. Centering respects the requested window geometry and clamps it to the scaled Windows work area.
- Fast dashboard metrics and slow hardware metadata run in separate worker groups. Static metadata caching uses monotonic time and stamps the cache after the query finishes. Battery bytes are unsigned, unknown/no-battery readings return `(None, 'Unknown')`, and GetTickCount64 has an explicit unsigned 64-bit return type. CPU count is labeled as logical processors.
- Worker callbacks enter a bounded queue. Only the creating thread can drain it. Workers never call Tk, including after(0). Expendable pending callbacks are bounded to 512, keyed metric/progress updates can coalesce, critical completion callbacks survive log pressure, and each displayed or buffered section log retains at most 500 lines. Closing discards pending/late callbacks.
- Maintenance uses a shared operation group held until result delivery completes. Duplicate/conflicting operations are refused; update download and installation block maintenance, while a background release check permits maintenance. Controls reset after worker errors. Newly opened sections also reflect the current busy state.
- Cleanup preview exposes skipped/error counts and partial inspection. Temporary deletion, Recycle Bin deletion and network reset each require explicit confirmation. Privileged battery-report and classic Control Panel launches resolve Windows system executables rather than cwd/PATH and use argv with shell=False.
- Turbo reads actual states, leaves unknown settings labeled Unknown and disabled, serializes mutations through the maintenance group, invokes persisted-original-state restoration APIs and refreshes actual state after either success or failure. The power setting explains increased power use, heat and battery drain.
- Resurrection uses the maintenance domain's strict run_sequence contract. Verified restore creation is the first critical prerequisite; failure halts before file deletion or network changes. Progress advances after each completed attempt, every completed step records a result, cancellation is checked between commands, and completed/partial/failed/cancelled summaries remain visible after the buttons reset. No implicit System Restore enabling occurs.
- Removed legacy UI executable swap, generated helper cleanup, old-executable deletion and direct update HTTP implementation. Manual/startup checks use UpdateClient; release notes, defer and retry are available. Source execution opens the validated release page. Frozen execution downloads/verifies, invokes the trusted self-update helper, polls its status and closes the old app only after readiness is acknowledged. The old app stays open on failures.

## Consumed interfaces

`UiDispatcher(max_pending=512).post(callback, *args, key=None, critical=False)`, `.drain(limit=100)`, `.close()`; `WorkerController.start(name, work, group='maintenance', on_success=None, on_error=None, on_done=None)`, `.busy(group)`, `.close()` and `.join(timeout)`.

`SystemMonitor.sample_fast()` returns a dict with ram, disk, cpu, uptime and battery. `sample_metadata()` returns os, cpu_name, ram_info and disk_model. UI metric readiness hook is `_update_fast_gui(sample)`; slow metadata hook is `_update_metadata_gui(sample)`.

CleanupManager tuple signatures and last_result.count/bytes/skipped/errors/ok; PerformanceManager existing getters and setters plus set_turbo/is_turbo_active; OperationStep/run_sequence; UpdateClient.check/download; Release.release_url/version; start_self_update(staged,target,release,client) and SelfUpdateJob.poll status/message are integrated without modifying their owning files.

## Test evidence

Initial domain implementation used mocked Tk boundaries. After the controller discovered a real 200x200 mapped-window regression, the controller explicitly authorized two real Tk layout tests. These replace every manager constructor and startup system/network query before app initialization, then map and destroy the real window. No native maintenance command was executed and no host power/service/registry/cleanup mutation was performed. Queue behavior uses real threads.

Watched failing tests before implementation covered missing dispatch/guard behavior, slow-metadata separation, wall-clock cache use, truncated uptime and signed battery bytes. Additional watched failures covered unsafe maintenance during download, duplicate Resurrection clearing cancellation, misleading successful preview, centering geometry, PATH-resolved powercfg, lazy section creation and cached Turbo state before section creation.

Final commands, all exit 0:

- Before the real mapping regression was added, `python -m pytest tests/test_ui_dispatch.py tests/test_system_monitor.py tests/test_ui_controller.py --basetemp build/tests-ui -q`: 27 passed.
- `python -m pytest tests/test_ui_controller.py -k real_tk --basetemp build/tests-ui-real -q`, outside the restricted sandbox: 2 passed. Both tests first failed with the actual mapped width 200; the first mapping and subsequent minimum-size/user-resize checks now pass.
- Mapping-correction snapshot `python -m pytest --basetemp build/tests-ui-mapping-final -q`, outside the restricted sandbox: 166 passed in 4.45 seconds; no skipped tests or failures.
- `python -m ruff check panacea_ui.py modules/ui_dispatch.py modules/system_monitor.py tests/test_ui_dispatch.py tests/test_system_monitor.py tests/test_ui_controller.py --select F821,F822,F823,E9,W605`: All checks passed.
- `python -m py_compile panacea_ui.py modules/ui_dispatch.py modules/system_monitor.py`: passed.
- Importing panacea_ui, modules.ui_dispatch and modules.system_monitor without constructing a GUI: passed.

The restricted sandbox's real Tk creation exited with Windows invalid-handle exception 0xc0000008. The authorized test run outside that sandbox provided the RED and GREEN evidence; regular full-suite runs on this host now need a display-capable execution context for these two tests. A platform without a Windows/display session skips only those real Tk cases.

## Real sizing regression and correction

The controller's first after-final screenshots revealed that a withdrawn window could map at 200x200 even though geometry had requested 1020x680 or 1100x700. Reading CustomTkinter's geometry and Configure implementations confirmed that pending initial Configure events overwrite `_current_width` and `_current_height` during idle processing. The first mocked clamp tests did not exercise that lifecycle and therefore missed the regression.

Panacea now preserves explicit geometry requests in its own `_requested_window_size` through a geometry override. Centering captures that request before idle processing, computes the work-area clamp from it and restores native minimum-size enforcement. A later user resize remains honored. This change is backed by real mapped-window tests, not only arithmetic clamp tests. Fresh screenshot and benchmark evidence must use the corrected source; the earlier 200x200 captures are invalid layout evidence.

## Limits and remaining gates

- The final source screenshot matrix and startup samples are recorded below. Actual Windows display-DPI changes, packaged readiness and independent branch review remain separate controller/release evidence; synthetic CTk widget scaling must not be described as verified OS DPI behavior.
- Real elevated, prior-release packaged update migration remains a release gate. Automatic elevated replacement intentionally requires an administrator-protected installation directory; Desktop/Downloads installs receive the helper's refusal and manual-release-page fallback.
- Verified staged download files may remain in their unique temporary directory after a helper preparation failure. The UI removes only an empty operation directory; it does not enumerate/delete backup or updater files. Partial downloads are cleaned by UpdateClient. This deliberately avoids the unsafe legacy sweeping behavior.
- Cancelling Resurrection does not interrupt an already running native command. Closing sets cancellation/shutdown and ignores subsequent UI callbacks; an existing external command may continue.
- A settings launch has no completion result from Windows. Windows Update is opened for explicit user action; Panacea does not silently start an update installation.
- Controls and queue mechanics have deterministic mock/thread tests; initial mapping and user resize also have real Tk tests. Native Tk focus/rendering, Windows restore/service queries and readiness behavior still require the controller's environment checks.

## Reviewer finding: trusted startup PowerShell launch

The independent reviewer confirmed that the three monitor PowerShell launch sites inherited elevated cwd/PATH resolution. A writable working directory or PATH entry could therefore select a different executable during RAM metadata, disk metadata or Windows Update queries. The invariant is that all privileged monitor subprocesses launch the Windows system-directory PowerShell executable without a command shell.

All three queries now resolve `modules.commands.system_executable('powershell.exe')` and specify `shell=False`. Existing scripts, timeouts, return types and parsed results remain unchanged. Six watched RED tests cover each real subprocess boundary with an attacker-looking PATH and each trusted-resolution failure; all become GREEN after the narrow fix. Resolver failure performs no subprocess call and retains each query's existing unavailable/error result. A separate source review confirmed no bare PowerShell launch remains in this module; fixed scripts use `-NoProfile` and no attacker-provided shell arguments. No fake executable or native PowerShell command was executed by these tests.

Security-correction snapshot commands:

- `python -m pytest tests/test_system_monitor.py --basetemp build/tests-ui-monitor-security -q`: 11 passed.
- `python -m pytest tests/test_ui_dispatch.py tests/test_system_monitor.py tests/test_ui_controller.py --basetemp build/tests-ui-domain-final -q`, outside the restricted sandbox: 35 passed in 4.67 seconds.
- Scoped ruff, py_compile and git diff --check: passed.
- Fresh whole suite `python -m pytest --basetemp build/tests-ui-security-final -q`, outside the restricted sandbox: 172 passed and **2 failed** in 7.62 seconds. The failures are outside this domain: `tests/test_cleanup.py::test_inplace_junction_conversion_is_blocked_by_live_directory_guard` (junction conversion returned True) and `tests/test_cleanup.py::test_inplace_junction_conversion_is_blocked_during_preview` (preview counted 2 files/7 bytes rather than 1 file/3 bytes). They were immediately reported to the controller; this report does not claim the full branch is passing at this snapshot.

## Dashboard viewport correction and current evidence

The controller's valid 1366x768 / 150% screenshot showed that the original two-row dashboard placed disk usage and primary quick actions below the initial viewport. This was an unmet presentation requirement even though navigation and arithmetic-clamp tests passed.

The dashboard now presents CPU, memory and system disk as three peer cards in one row. A compact full-width quick-action card places Preview temporary files, Create restore point and Open cleanup horizontally below them. The dashboard header and chart heights are restrained, the CPU/RAM history graphs remain present and resize, and secondary hardware/storage text wraps using logical widget units. Scrolling remains available for genuinely smaller viewports or longer secondary information.

A real Tk parameterized regression uses fixture managers and realistic metric/metadata values at physical 1366x768 with 150% widget/window scaling and 1020x680 with 100% scaling. Before the correction, the 150% case failed because the disk percentage was below the viewport. After correction, both cases pass. Bounds checks cover all three primary metric values, all three action buttons and the entire quick-action card; they verify both horizontal and vertical visibility without scrolling. No maintenance button is invoked.

Current final commands, all exit 0:

- `python -m pytest tests/test_ui_dispatch.py tests/test_system_monitor.py tests/test_ui_controller.py --basetemp build/tests-ui-dashboard-final -q`, outside the restricted sandbox: **37 passed in 3.43 seconds**.
- `python -m pytest --basetemp build/tests-ui-dashboard-all -q`, outside the restricted sandbox: **190 passed in 6.23 seconds**, with no skipped tests or failures. This supersedes the earlier two cleanup-junction failures recorded above; those failures were outside this domain and were corrected by the coordinating work.
- Scoped ruff, py_compile and git diff --check: passed.

Earlier matrix images are retained as the trigger for the correction. The final source evidence below captures the corrected layout.

## Final native source screenshot matrix

The controller delegated final source evidence after freezing the product UI. scripts/visual_check.py was used with physical width/height arguments, `ctk.set_window_scaling(1)`, widget factors 1.0/1.25/1.5, and an 8000ms initial settle so hardware metadata was populated. The only harness change is an optional `--settle-ms` argument whose default remains 2500ms. Each view settles another 300ms before Pillow captures the actual Windows screen pixels. These are native source-app captures, not design mockups.

All 42 images were inspected. Every observations.json reports the requested physical pixel dimensions and an empty callback_errors list. [final-matrix.json](screenshots/final-matrix.json) contains all paths, image SHA-256 values, UI/monitor source hashes and inspection notes.

| Physical window pixels | CTk widget factor | Views | Dashboard | Native observations |
|---|---:|---:|---|---|
| 1366x768 | 1.0 | 7 | [PNG](screenshots/final-1366x768-100/dashboard.png) | [JSON](screenshots/final-1366x768-100/observations.json) |
| 1366x768 | 1.25 | 7 | [PNG](screenshots/final-1366x768-125/dashboard.png) | [JSON](screenshots/final-1366x768-125/observations.json) |
| 1366x768 | 1.5 | 7 | [PNG](screenshots/final-1366x768-150/dashboard.png) | [JSON](screenshots/final-1366x768-150/observations.json) |
| 1920x1080 | 1.0 | 7 | [PNG](screenshots/final-1920x1080-100/dashboard.png) | [JSON](screenshots/final-1920x1080-100/observations.json) |
| 1920x1080 | 1.25 | 7 | [PNG](screenshots/final-1920x1080-125/dashboard.png) | [JSON](screenshots/final-1920x1080-125/observations.json) |
| 1920x1080 | 1.5 | 7 | [PNG](screenshots/final-1920x1080-150/dashboard.png) | [JSON](screenshots/final-1920x1080-150/observations.json) |

The seven files in each directory are dashboard.png, cleaning.png, disk.png, tools.png, apps.png, turbo.png and resurrect.png. Capture command form: `build/release-venv/Scripts/python.exe scripts/visual_check.py --output docs/validation/screenshots/final-<resolution>-<factor-label> --width <physical-width> --height <physical-height> --scale <widget-factor> --settle-ms 8000`.

Inspection results:

- CPU, RAM and disk values plus all three primary quick actions fit the initial dashboard viewport in all six combinations. OS, CPU, RAM and disk metadata are populated; graphs and storage bar are visible.
- Active sidebar selection is clear on all seven screens. Cleanup, Disk, Apps and Resurrection actions and their explanatory text fit without horizontal clipping or overlap. Log areas remain empty because no maintenance action is invoked.
- Tools intentionally scrolls separately from its visible execution log. At 1366x768, network/utilities require scrolling at higher widget factors; the utility row can sit at the scroll-pane boundary even at factor 1.0. At 1920x1080/factor1.5 the utility row remains below that pane's initial fold. This is a remaining density limitation, not a blocked action.
- Turbo's lower settings require normal vertical scrolling at 1366x768/factors1.25 and1.5. All settings plus Refresh are visible at 1920x1080/factor1.5. Existing active power state is displayed without changing it; master/individual switches are never invoked by the capture harness.
- Windows Update can still show checking after the eight-second settle because its read-only query has a longer timeout. The captures do not assert check completion or any update installation.
- **Actual OS DPI changes: NOT RUN.** Only synthetic CustomTkinter widget factors were varied; Windows display settings were not changed. The matrix does not replace a true 100/125/150% OS-DPI acceptance test.

Five-sample source timing evidence and its tail-latency caveat are in [performance-report.md](performance-report.md). The final repeat ran after the controller confirmed build/test completion: median ready 0.864890s, first metric 0.658503s, heartbeat p95 13.461000ms and maximum 194.309500ms. All five windows were 1020x680 and every individual JSON matches the retained summary. The earlier pre-build cohort remains preserved; the final report treats heartbeat p95 as similar to baseline rather than claiming the earlier large improvement. Existing process-only idle measurements are explicitly intermediate evidence taken before final cleanup-boundary edits and exclude child processes.

No UAC, cleanup, repair, Turbo mutation, updater installation or Windows settings change was performed during these source evidence runs.

No commit, branch mutation or release publication was performed by this domain.

## Monitor query shutdown correction

CI run 38272755049 passed its checks but runner orphan cleanup still terminated PowerShell/conhost after packaged smoke closure. The completed green cac08c8 snapshot is therefore intermediate evidence, not proof of correct query shutdown. Source inspection found that daemon monitor workers used unowned check_output calls and Tk shutdown did not cancel them.

The three read-only queries now share a thread-safe owned-Popen registry. The closed check, process creation and registration are atomic under one short lock. SystemMonitor.close immediately marks the monitor closed and starts one non-daemon cancellation/reap thread, so Tk never waits for CreateProcess, communication or reap. That thread waits for any already-started constructor to register, kills only owned query handles and waits with a two-second bound per child. Queries started after closure are refused. The owning query worker closes its own stdout/stderr streams after reap; the cancellation thread never closes a pipe while its reader is active. TimeoutExpired and the existing query parsing/error contracts remain intact, with trusted executable argv and shell=False preserved. PanaceaApp calls monitor.close before destroying Tk; the update-replacement close guard remains in force.

Watched RED-to-GREEN checks cover off-caller-thread cancellation, no launch after close, close during a held constructor, timeout, failed Popen, communication failure, the UI close hook and native timeout pipe cleanup. Two native fixtures launch only the current Python executable with sleeping scripts inside temporary test directories: closure is verified to kill and wait the owned child, and timeout is verified to reap the child and close stdout/stderr. No real PowerShell or maintenance command is invoked by those fixtures.

Fresh isolated-runtime verification: 19 monitor tests passed; the complete UI-domain suite passed **47 tests in 4.90s**; the full repository suite passed **231 tests in 7.55s**, with no skipped tests or failures. Scoped ruff, py_compile and git diff --check passed. Existing real Tk viewport cases, including the hosted-runner wmmaxsize fixture, were retained.

This correction does not alter presentation. The earlier screenshot/benchmark evidence remains retained at its measured revision; no full matrix recapture or benchmark was performed in this narrow shutdown task. A fresh package/smoke/CI run must directly confirm that production PowerShell/conhost orphans no longer remain.

Parent final verification after source freeze: all231 repository tests, Ruff and compilation passed again. Seven current-source views were recaptured and inspected in screenshots/release-final-1366x768-150, at1366x768 with widget factor1.5/window factor1.0. Zero callback errors; core dashboard metrics/actions remain in view and hardware captions are populated. Tools and lower Turbo controls retain the documented scroll behavior. The earlier42-image six-condition matrix remains at its recorded revision; this one-line shutdown hook and query ownership change did not change presentation. Actual OS DPI remains unrun.

Five refreshed source samples and five rebuilt safe EXE launches passed; final measurements and package digest are in performance-report.md and candidate-package.json. Final remote CI/orphan verification is recorded in the task handoff.

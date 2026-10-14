# Maintenance safety validation

Date: 12 October 2026. Branch: `codex/panacea-next-generation`.
Environment: Windows 11, build 10.0.26300, AMD64, Python 3.14.3, pytest 9.0.2.

## Changes and contracts

- `modules/cleanup.py`: accepts only the current profile's conventional local Temp directory and the Windows Temp directory resolved through the native Windows API. Broad, relative, network, device, relocated or unapproved roots are refused. Chrome/Edge Default Cache and Code Cache, plus Firefox profile cache2, are explicit browser targets. Every ancestor and traversed directory is opened without following reparse points and held against writes, in-place reparse conversion, rename and deletion. Existing incompatible writers make the operation fail closed. Individual regular files are verified and deleted through their Windows handle. Junctions, symlinks, multiply linked files, locked entries and other unverified entries are skipped. Empty directories are retained. Counts increase only after successful file deletion; byte totals are the removed files' logical sizes, not a measured increase in physical free disk space.
- `CleanupManager.preview_temp_files()` returns `(count, bytes)` without deleting files. Existing cleanup tuple returns and `progress_callback` remain. `last_result` is a `CleanupResult` with `count`, `bytes`, `skipped`, `errors`, `preview` and `ok`; `ok` is false when anything was skipped or failed. Skips and errors contain path/reason strings.
- `modules/commands.py`: exact allowlist for SFC, DISM health/repair/component cleanup, DNS flush, Winsock reset and CHKDSK scan/perf. Direct trusted Windows executable paths and argument arrays replace CMD/shell interpolation. Unknown commands, shell fragments and invalid drive values fail before process creation. Stream output is drained even when a presentation callback fails. `run_command_stream` returns a verified exit-code boolean. `run_command` returns launch success only and does not claim completion.
- `modules/disk.py`: requires exactly a drive letter with colon, for example `C:`. Defrag uses direct arguments, always drains stdout, and returns a success boolean. Windows utility launches also use trusted executable paths.
- `modules/performance.py`: setters save originals before any mutation, verify outcomes and restore those originals rather than applying defaults. The recovery file is `%LOCALAPPDATA%/Panacea/turbo-state.json`; state reads do not create directories or change settings. Flushing/fsync precede atomic same-parent native replacement by source handle, without resolving a mutable destination directory path. Storage directories are pinned against writes/path replacement and reparse roots are refused before writes. Invalid/unavailable records prevent changes. Custom power GUIDs, originally stopped services and exact DWORD visual values survive manager re-instantiation. Missing/unqueryable settings return `None`. Existing setters return `(bool, message)`. Missing recovery records cause a restore request to leave the actual setting untouched. All setters, including the master, share a process-wide reentrant lock and a reentrant Windows Global named mutex keyed by the canonical recovery-file path; the record reloads under this transaction before setting queries, snapshot writes or mutations. A bounded lock timeout returns failure without querying/changing settings. An abandoned owner releases the lock, and the next holder reloads durable recovery before proceeding.
- `PerformanceManager.set_turbo(enabled=True)` captures every original before changing any master setting, returns `(bool, message)`, and retains recovery records after failure. `is_turbo_active()` returns `bool | None`; an active configuration without a complete recovery record is unknown. `get_power_plan()` retains `high`, `balanced`, `other`, and adds `None` for a failed query. Other existing getters return actual `bool | None` values. Optional constructor `logger` and `state_path` support controlled integration/testing.
- `modules/restore.py`: point creation never enables System Restore implicitly. It requires a queryable initial sequence and a strictly larger verified final sequence. A successful empty query is represented by sequence zero, permitting verification of the first point; unknown/query failures remain `None`. Unchanged, decreasing, missing or unqueryable sequences fail. Explicit `ensure_restore_enabled` validates a drive root and checks the PowerShell exit code. Descriptions are bounded, quoted as literal PowerShell strings and reject control characters; query limits are validated integers.
- `modules/operations.py`: `OperationStep(name, action, critical=False)` and `run_sequence(steps, cancel=None, progress=None)` return `OperationResult(status, steps, error)`. Each `StepResult` contains name/success/message. Actions must return bool or `(bool, message)`. Critical failure prevents later steps; cancellation is checked only between completed commands. Progress receives `(completed_count, total_count, StepResult)` after each step finishes. Terminal statuses are completed, partial, failed and cancelled.

## Test evidence

All tests patch logging with a null logger. Filesystem operations use disposable fixture directories; Windows power/service/registry/restore/repair subprocess changes are mocked. The actual user's Temp, browser cache, Documents, power plan, services, registry, recycle bin and restore configuration were never used as test targets. Native Windows directory/path reads are read-only.

Initial cleanup/command tests were run against the original implementation: 19 failed and 2 passed. The failures demonstrated broad-root deletion, junction traversal, nested-file undercounting, missing preview/skips, injected command launches and missing disk validation/results. After the first fixes, all 21 passed.

Initial Turbo/restore tests: 13 failed and 1 passed. They demonstrated loss of custom power/service/visual originals, failed-query defaults, service-name injection, missing snapshot persistence, false restore success and implicit enablement. After implementation, the combined scoped suite reached 35 passing tests. The new operation sequence module was initially absent; its five contract tests then passed after implementation.

A real rename regression test exposed a Windows sharing-rule issue: an attribute-only directory handle allowed rename despite omitting FILE_SHARE_DELETE. A controlled temporary-directory probe produced `access 128: rename allowed` and `access 129: rename blocked, WinError 32`. Adding FILE_LIST_DIRECTORY to the held directory access fixed the failure. The final rename test verifies the attempted swap is blocked while a file is deleted. Microsoft's [CreateFile documentation](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew) explains the access/sharing distinction.

A recovery-directory junction test first failed because snapshot writes followed the junction and the mock power setting changed. Guarded directory creation/storage fixed that test; the outside directory remains empty and the original mock power scheme remains unchanged.

Final scoped command:

```text
python -m pytest tests/test_cleanup.py tests/test_commands.py tests/test_performance.py tests/test_restore.py tests/test_operations.py -q --tb=short --basetemp build/tests-safety
53 passed in 0.45s
```

The scoped cases cover unsafe TEMP, native NTFS junction roots/descendants, outside sentinels, real Windows locked files, hardlinks, directory rename attempts, preview, deletion counts, browser target isolation, command/drive injection, exit failures, exact recovery after restart, unknown/corrupt/write-failed recovery, reparse storage, conflicting setters, critical failure, cancellation, exceptions, partial results and progress timing.

Whole-suite command at integration time:

```text
python -m pytest -q --tb=short --basetemp build/tests-safety-full
150 passed in 1.25s
```

The earlier full-suite run during concurrent UI implementation had 136 passing and seven failing tests in `tests/test_ui_controller.py`: restore prerequisite, persistent partial failure, cancellation, cleanup errors, unknown Turbo queries, cancelled cleanup confirmation and source update behavior. The 150-test run above contains those tests and was green.

A subsequent rerun while the UI agent added another batch of regression tests produced **157 passed, 5 failed**. The five current RED tests belong to ongoing UI work:

- `tests/test_ui_controller.py::test_centering_preserves_requested_geometry_when_it_fits`
- `tests/test_ui_controller.py::test_centering_clamps_large_geometry_to_scaled_work_area`
- `tests/test_ui_controller.py::test_battery_report_uses_system_directory_and_single_output_path`
- `tests/test_ui_controller.py::test_navigation_builds_each_section_only_when_first_opened`
- `tests/test_ui_controller.py::test_actual_turbo_state_is_cached_before_section_is_built`

Immediately before that run, collection encountered a transient raw-string syntax error in the same concurrently edited UI test file; the UI agent corrected it. The safety agent has reported all five current failures to the UI agent and controller without editing their owned files. The controller must run the integrated suite again after those implementations are complete. This report does not claim the current whole branch is green.

Compile validation:

```text
python -m compileall -q modules/cleanup.py modules/commands.py modules/disk.py modules/performance.py modules/restore.py modules/operations.py
exit 0
```

Some sandboxed fixture runs intermittently denied NTFS junction/hardlink creation. Verification was repeated with approved unsandboxed execution against the same workspace fixture roots; all 53 scoped cases ran and passed, with no skips. No maintenance action was authorized or executed on the host to obtain this evidence.

## Limits and pending release validation

- Real elevated power switching, service transitions, registry updates, System Restore enable/create/throttling and repair commands are NOT RUN. Mocks prove orchestration and failure handling; release verification must separately establish real Windows behavior with explicit approval for system changes.
- The command decoder preserves the existing encoding fallback; localized service output that cannot be interpreted returns unknown and prevents mutation. Service transition verification is bounded to five seconds, then fails with the original retained for retry.
- Custom relocated Temp/LOCALAPPDATA directories, network cleanup roots and non-Windows cleanup/recovery are conservatively refused. Browser targets preserve the existing Default-profile scope; additional Chrome/Edge profiles are not inferred.
- Turbo processes that use the same recovery store now share a cross-process transaction lock. Deliberately different stores or different user profiles have separate identities; recovery records remain ordinary per-user files, not authenticated storage against a malicious process running as that user.
- Cleanup byte totals describe logical payload removed; compressed/sparse files, open readers and filesystem allocation can change physical space reclamation. User confirmation for irreversible cache/recycle deletion and network reset belongs to the UI, and requires the controller's end-to-end validation.
- No changes were committed by this agent. Independent final review, real Windows release evidence and publication gates remain with the controller.

## Independent review follow-up

The independent reviewer and controller found that the initial directory guard allowed FILE_SHARE_WRITE. A malicious writer could convert an already-open empty directory into a junction through FSCTL_SET_REPARSE_POINT after the one-time reparse check, redirecting path-based traversal. Two real disposable native regression tests reproduced this without any deletion: conversion succeeded under the held guard, and preview counted the outside sentinel (`2 files / 7 bytes` instead of `1 file / 3 bytes`). Both tests were RED before the fix. Held directory/read-preview handles now permit FILE_SHARE_READ only. The conversion attempt fails with WinError 32, the outside sentinel stays intact, and legitimate nested deletion and preview controls remain green.

The tighter directory guard initially prevented path-based snapshot replacement, whose destination-directory reopen requests write access. A controlled fixture probe confirmed that a source-handle rename with a simple same-parent name succeeds while the parent remains pinned. Persistence now uses [NtSetInformationFile](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntsetinformationfile) with [FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information), binding the destination to the source's existing directory object. Existing original-state persistence and restoration controls pass with this path guard still held.

The reviewer also identified snapshot loss between independent app processes. Three fixture-only child-process regressions first failed: a competing manager queried/changed mock settings while another process owned a pending snapshot; a restore ran before the other owner terminated; and a contention timeout still changed settings. After the Global named mutex transaction was added, the competing process waits, stale managers reload and preserve both original keys, killed owners release the lock and permit exact recovery, and timeout makes zero settings queries/writes. Existing master Turbo tests verify nested setters remain reentrant.

Fresh post-fix scoped command:

```text
python -m pytest tests/test_cleanup.py tests/test_commands.py tests/test_performance.py tests/test_restore.py tests/test_operations.py -q --tb=short --basetemp build/tests-safety
58 passed in 1.67s
```

Post-fix compile and diff checks pass. A full-suite run produced **189 passed, 1 failed**: `tests/test_ui_controller.py::test_real_tk_dashboard_primary_metrics_and_actions_fit_initial_viewport[1366-768-1.5]`, where the `75.0% used` label extends below its initial viewport. The controller was informed. This full suite now includes real Tk layout cases added after the original implementation; subsequent real-GUI verification remains with the controller. No host configuration was changed. A fresh independent bypass/regression review remains pending.

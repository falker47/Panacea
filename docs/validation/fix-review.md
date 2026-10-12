# Independent candidate bypass and regression review

Reviewed 2026-10-12 against `build/validation/fix-review-package.txt` and the current implementation. No previous review, implementer report, or claimed test results were used. This was the single fresh candidate review requested by the parent. Product files, index, and HEAD were not edited; no GUI or host maintenance was launched.

## Result

No concrete surviving bypass or regression was established within the five assigned findings. All five are **ADDRESSED**, with the execution limits below. This is an implementation review, not certification of a built executable or a substitute for release verification.

| Finding | Disposition | Independently checked evidence |
| --- | --- | --- |
| Directory conversion during cleanup | **ADDRESSED** | `modules/cleanup.py:42` opens a non-reparse handle with read sharing only. `_guard_path` at line 75 pins every ancestor; recursive traversal at line 161 holds each child directory through enumeration and descent. Live conversion and rename fixtures pass, alongside legitimate deletion and preview. |
| Separate processes losing Turbo originals | **ADDRESSED** | `modules/performance.py:21` uses a named Windows mutex keyed by normalized real state path; `_transaction` at line 71 reloads durable state after ownership. Individual and master changes hold ownership through capture/save/mutation/verification. Real child-process contention, timeout, abandoned-owner recovery, and exact restoration fixtures pass. |
| A transient readiness-cleanup lock permanently blocking updates | **ADDRESSED** | `modules/update_install.py:163` validates token, target, generated backup identity, protection mode, installed digest, and existing backup digest. The finalizer at line 192 retries only completed records. The installer invokes it at line 249 before beginning a new operation. Backup-lock and marker-lock recovery fixtures both pass. |
| Initial withdrawn Configure collapsing the main window | **ADDRESSED (source and non-GUI checks)** | `panacea_ui.py:849` captures explicit requested geometry independently of CTk's mutable current dimensions; `_center_and_show` at line 858 consumes that request before flushing pending layout events and reapplies the fitted dimensions before mapping. Real Tk execution was excluded by review scope. |
| Startup monitor launching bare PowerShell under elevation | **ADDRESSED** | All three subprocess sites (`modules/system_monitor.py:76`, `:123`, `:247`) use `system_executable('powershell.exe')`, `shell=False`, and `-NoProfile`. The shared resolver (`modules/commands.py:10`) derives the absolute system PowerShell location from `GetSystemDirectoryW`. Result parsing and resolution-failure/no-fallback fixtures pass. |

## Boundary and compatibility checks

Cleanup must never traverse a reparse directory or let an ancestor become one while path-based enumeration is active. The guard now denies both write and delete sharing, checks the opened object's attributes, and closes handles through context-manager cleanup. A junction already present is refused. Renaming a pinned directory fails. File deletion uses the held file handle and rejects multiply linked files. Legitimate nested deletion, preview counts, and explicit browser cache cleanup still pass. Preview and actual cleanup share the directory enforcement boundary.

Turbo is the important sibling consumer of this stronger guard. Its snapshot replacement no longer reopens the pinned parent with a conflicting write request. `modules/performance.py:151` builds a native FileRenameInformation request with a simple basename, null root, and the temporary file's held source handle. Tests exercised real native snapshot creation and replacement, including exact restoration of custom power GUID, visual value 3, and an originally stopped service. The original is fsynced before settings change; failed save prevents mutation. WAIT_ABANDONED grants ownership but the caller reloads the snapshot before acting. Nested master/individual transactions occur on the same owning thread and balance acquisitions/releases. The timeout test verifies no setting query or mutation happens while ownership is unavailable.

Updater housekeeping must distinguish an acknowledged operation from a pending or foreign operation. Pending, forged, checksum-mismatched, and wrong-token records remain blocked without discarding their backups. A successful acknowledgment is recorded before cleanup; a lock leaves that record available for a future retry. If backup deletion succeeds but marker deletion is locked, validation permits a missing backup only for a ready record. `_operation_ready` (`modules/update_install.py:559`) scopes subsequent helper activity to its own token and backup: the later-operation fixture confirms an older helper does not remove the newer marker or terminate its process. Timeout and rollback paths also revalidate operation identity under the transaction guard. Production protected operations use the named mutex; unprotected fixture operations use the in-process lock.

The version remains `1.49.0`; the UI still constructs the seven CustomTkinter sections (`panacea_ui.py:83`). The reviewed workflows retain exact `Panacea.exe` and `Panacea.exe.sha256` assets, source/version checks, and packaged smoke checks. These source contracts were inspected; no release build or publication was performed.

## Commands and observed results

- AST parsing of the seven affected runtime files: **passed** (no bytecode output).
- `python -B -m pytest -q -p no:cacheprovider tests/test_cleanup.py tests/test_performance.py tests/test_update_install.py tests/test_system_monitor.py tests/test_ui_controller.py -k 'not real_tk'`: default sandbox temporary directory was unavailable; 33 passed and 60 fixture-setup errors. This did not establish product failures.
- The same command with `--basetemp=build/validation/reviewer-fixtures-20261012`: 88 passed, 3 skipped, 4 deselected; two fixture setup/control failures because the sandbox denied hardlink/junction creation.
- The same focused suite with `--basetemp=build/validation/reviewer-native-fixtures-20261012`, outside the sandbox after automatic approval: **93 passed, 4 deselected**. This includes actual Windows handles, junction conversion controls, native snapshot replacement, child-process mutex contention/abandonment, and fixture installation/readiness/rollback. Maintenance commands and registry writes are mocked; updater launches are injected.

## Remaining proof gaps

- Four real-Tk tests were deliberately deselected; no visible GUI, packaged smoke, or build was run. Startup geometry therefore has source and non-GUI evidence in this review, not independently observed mapping behavior.
- Updater helper fixtures replace privileged ACL creation/validation and the protected transaction guard. Actual protected updater mutex concurrency and ACL behavior were source-reviewed, not exercised end to end by this suite.
- The native cleanup control exercises a GENERIC_WRITE reparse-conversion open. An additional disposable probe of alternate access masks was **not executed**: automatic approval review rejected it because it creates files/directories and calls `FSCTL_SET_REPARSE_POINT`, exceeding the delegated read-only-probe wording. No workaround was attempted. Additional authorization would be needed to execute that optional probe; this is an untested edge, not a demonstrated bypass.
- Local tests used Python 3.14; the workflows specify Python 3.12. Process abandonment was tested; abrupt machine power loss and full filesystem crash durability were not simulated.

Only this report was added as retained review output. Disposable pytest fixtures remain under the two explicitly named `build/validation/reviewer-*` directories.
# Subsequent parent validation

This scoped report predates the FILE_WRITE_ATTRIBUTES variant. Later parent fixture execution proved that variant bypassed the earlier share-mode repair. The completed boundary correction and fresh review/precondition evidence are in final-security.md; the earlier all-addressed conclusion is not a current unqualified security signoff.

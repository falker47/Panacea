# Independent candidate code review

Date: 2026-10-12. Candidate: 1.49.0. Base: `d605d5c8f135b49ca20c75b85845bf216b648ef0`.

Reviewed immutable package: `build/validation/review-package.txt`, SHA-256 `bc56735146fab0774c706009d7552e7619c5f1053bdf023d0c3b188b66efffb8`. Source line references below refer to that snapshot, not later integration fixes. Scope included the design and implementation plan, maintenance modules, updater/helper, entry point, UI/dispatcher, packaging/workflows, and regression tests. Product sources, Git index and branches were not modified by the reviewer.

## Verdict

**Changes required: one Critical and four Important findings.** Do not promote this snapshot to a stable release. The existing 163-test pass, Ruff and compile/import results were supplied by the controller; the reviewer did not rerun unchanged suites. Passing those checks does not cover the concrete failures below. The controller separately observed a real-window geometry failure during this review and is correcting it; that correction is outside this immutable snapshot.

## Critical

### C1 — A held cleanup directory can be converted into a junction in place

Location: `modules/cleanup.py:57-67`, `modules/cleanup.py:160-180`; the same directory guard is reused by `modules/performance.py:63-105`.

The non-delete directory handle allows both `FILE_SHARE_READ` and `FILE_SHARE_WRITE` (`share=3`). Omitting delete sharing prevents rename, but does not prevent another writable handle from applying `FSCTL_SET_REPARSE_POINT` to that same empty directory. The code checks the reparse attribute only when acquiring the handle, then enumerates and opens descendants through ordinary paths. A local process able to modify a cleanup subtree can turn an opened empty child into a junction after the attribute check, redirecting the elevated cleaner to files outside the approved root. Holding all ancestor handles does not stop this in-place change. This invalidates the central “never delete outside approved roots” contract and also weakens the shared Turbo storage guard.

**Evidence:** A narrow native Windows fixture probe created `held`, `baseline` and `outside` under `build/review-reparse-q5qqjanp`, with one read-only sentinel payload in `outside`. Applying a mount-point reparse buffer through a separate `GENERIC_WRITE` handle succeeded both without the guard and while `_guard_path(held)` was active. Ordinary enumeration of `held` while that guard remained active returned the outside sentinel:

```text
without_guard (True, 0)
with_guard (True, 0)
guarded_entries ['sentinel.txt']
outside_sentinel_unchanged READ ONLY PROBE
```

The probe invoked no cleanup/deletion and changed no host setting. The first sandboxed probe denied junction creation even without a guard, so it was inconclusive; the fixture-only repeat received automatic approval and established the result. Fixture paths remain under `build` for inspection; do not recursively delete them through a tool that follows junctions.

**Fix:** Prevent write access that can mutate held directory reparse metadata throughout traversal (for example, deny write sharing on directory handles and fail closed if an incompatible writer already exists), or implement handle-relative traversal with equivalent guarantees. Do not merely recheck attributes once: another race remains after that check.

**Regression:** In a disposable Windows fixture, attempt in-place junction conversion after the directory handle is acquired. Assert mutation is refused or traversal refuses the path, and assert an outside sentinel cannot be reached/deleted. Cover conversion of an ancestor and a nested child, and reuse the check for Turbo storage. Existing rename/junction-before-open tests do not exercise this race.

## Important

### I1 — Successful readiness with a locked backup permanently blocks later updates

Location: `modules/update_install.py:195-204`, `modules/update_install.py:496-502`, `modules/update_install.py:140-141`.

`acknowledge_ready` sets `ready=true`, then suppresses failure to delete the backup/marker. The helper accepts that acknowledgment and exits without retrying cleanup; no normal-startup recovery/finalization path exists. `install_verified` subsequently rejects every existing marker, including a valid completed one. The old UI intentionally remains running until acknowledgment, making an in-use old executable a natural source of the cleanup lock. A temporary antivirus or filesystem lock causes the same permanent block even if the normal executable-lock behavior differs on a particular Windows build.

**Evidence:** A tiny PE fixture install with an injected `PermissionError` on backup unlink returned `True` from readiness. After removing that injected lock, the next install still returned:

```text
next_install_after_lock_released False A previous update is still awaiting readiness. Keep its backup.
```

Fixture: `build/review-mocks-tz6my_bm`. No executable was launched. The existing `test_readiness_cleanup_failure_keeps_backup_and_records_ack` verifies retention but never verifies subsequent recovery.

**Fix:** Add an idempotent finalizer for authenticated/validated completed state, preserving backups until readiness and deleting only paths tied to the recorded operation. Retry after the original process has exited, or finalize a valid acknowledged record before accepting another update. Handle “backup deleted but marker deletion failed” separately as well.

**Regression:** Simulate successful acknowledgment while backup deletion is locked; release the lock, finalize and install another release successfully. Also simulate failure on marker deletion after backup deletion. Verify unacknowledged, forged and mismatched records retain fail-closed behavior.

### I2 — Concurrent application processes can overwrite the exact Turbo original

Location: `modules/performance.py:22`, `modules/performance.py:171-188`, `modules/performance.py:257-272`; `main.py` has no single-instance gate.

The class-level `threading.RLock` serializes manager instances only within one Python process. Two Panacea processes have independent locks and can both load an empty recovery record. If process B saves a custom power GUID and enables High Performance before process A reads the current setting, A subsequently saves High Performance as the original, overwriting B's record. Restoring then reports success while leaving the custom original lost. Similar overlapping writes can drop originals for different settings. Re-instantiation tests and the existing two-thread test share one process lock and cannot catch this.

**Evidence:** A deterministic safe model gave two managers the independent locks they would have in separate processes, paused A after loading state, completed B's mocked activation, then resumed A. Real temporary recovery-file persistence was used; all power reads/writes were in-memory functions. Both activations succeeded; the persisted `power` was `8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c`, replacing initial custom GUID `12345678-1111-2222-3333-123456789abc`. Restore returned success and retained High Performance. Fixture: `build/review-mocks-tz6my_bm`.

**Fix:** Hold an appropriate cross-process mutex/file lock for the entire read-original/persist/mutate/verify transaction, including the master operation, or enforce one active maintenance instance with a design that accommodates update handoff. Machine-wide power/services also need a coherent policy for separate Windows user sessions, because their current recovery files are per-user.

**Regression:** Use two subprocesses with mocked machine state and a synchronized shared recovery fixture to force this interleaving, then assert the exact original survives. Cover changes to different keys, master versus individual changes, and abandoned-lock recovery without touching real system settings.

### I3 — Initial Configure events collapse the usable window to 200 × 200

Location: `panacea_ui.py:844-855`.

`_center_and_show` calls `update_idletasks()` before using CustomTkinter's `_current_width`/`_current_height` as the requested design size. An initial Configure event can replace those fields with Tk's initial 200 × 200 dimensions; the method then explicitly applies those dimensions. The controller's real screenshot QA reported all final matrix windows at 200 × 200 despite requested sizes, consistent with this code. Existing tests mock those fields and the event pump, so they miss the event-order failure.

**Fix:** Preserve the requested logical design dimensions independently of transient Configure state, then clamp those dimensions to the physical work area and scaling. The controller reports this correction is in progress; it has not been assessed as part of this snapshot.

**Regression/evidence:** A real Tk lifecycle regression must allow Configure events to run and assert resulting usable dimensions. Recapture the seven sections and dimension/scaling matrix after the fix. The reported approximately 1.00-second `after-final` startup is not valid usable-window evidence until corrected and remeasured.

### I4 — Elevated startup still searches for an untrusted PowerShell executable

Location: `modules/system_monitor.py:75`, `modules/system_monitor.py:122`, `modules/system_monitor.py:246`; invoked automatically by `panacea_ui.py:100-104`.

The RAM, disk and Windows Update probes launch the bare executable name `powershell`. Windows process resolution can select a same-named executable from the application/current directory or search path. These probes run automatically after elevation, so a portable installation launched from a user-writable directory can execute an attacker-supplied executable with the app's privileges. This is inherited code, but remains an unresolved whole-candidate trust-boundary issue: the change adds and relies on the metadata sampling path while other modules now deliberately use a native-system-directory resolver.

**Fix:** Use `modules.commands.system_executable('powershell.exe')` in all three probes, preserving argument arrays and explicit noninteractive/profile options. Ensure no startup subprocess retains search-path executable resolution.

**Regression:** Mock `subprocess.check_output` and verify the executable is the trusted absolute Windows PowerShell path for each probe, even with hostile current-directory/PATH inputs. No payload execution or host mutation is needed.

## Minor

- `panacea_ui.py:829-838` removes only an empty download directory, but a successful verified download leaves an EXE inside. Failed/retried preparation accumulates those EXEs; helper workspaces additionally retain two full executable copies. Track exact operation-owned artifacts and clean completed/failed jobs conservatively, without scanning arbitrary updater/backup names. Pending rollback evidence must remain protected.
- Some validation documents retain earlier intermediate failing totals and limitations. The final handoff should identify the authoritative final run and explicitly supersede invalid 200 × 200 screenshots and startup measurements.
- `WorkerController.run` ignores a failed `dispatcher.post(..., critical=True)`. If a custom small queue or future expansion fills the queue exclusively with critical callbacks, an operation can remain busy forever. The present fixed set of app groups is far below the default 512-item capacity, so this is a robustness item rather than a current release blocker.

## Positive observations and limits

- Exact release filenames, authoritative version, bounded manifest/download reads, repository URL checks, checksum/PE checks, trusted protected helper context and revalidation are present. Unicode/spaced-path launch arguments use arrays; frozen UAC arguments use `list2cmdline`.
- Failure/rollback branches preserve evidence when replacement or launch fails. Launch acceptance is distinguished from readiness. A process that exits before acknowledgment is detected. These observations do not substitute for actual packaged Windows migration and lock testing.
- Queue-based worker delivery avoids direct worker Tk calls in reviewed operation paths; pending/late callbacks are discarded on shutdown, and maintenance groups remain held until completion delivery. Duplicate-click guards and result reporting are materially improved.
- Cleanup/Resurrection explicitly surface skips/failures, verify a restore point before destructive sequence steps, and honor cancellation between commands. Maintenance command allowlists and argument arrays remove the prior command-shell injection surface.
- Release preparation creates a draft only. There is no stable-publication job in this snapshot, so this review does not assert an implemented protected stable-publication environment. Green candidate CI, real Windows migration/security checks, and final human publication approval remain external mandatory gates.
- Not independently performed: a full security audit, actual elevated power/service/registry/restore/repair operations, real old-version EXE migration, antivirus/file-lock matrix, GUI launch/screenshot capture, signature validation, publication, or live ZEROfilez verification. The existing ZEROfilez latest/download/Panacea.exe contract was not changed by this review. Root-provided GUI observations are attributed above; all other narrow repros used disposable filesystem fixtures or injected state only.

The candidate is reviewable, but the Critical and Important findings require fixes and focused regression evidence before release consideration. This report is not a publication approval or a claim that Windows migration has passed.

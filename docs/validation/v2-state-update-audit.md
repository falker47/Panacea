# V2 Turbo state and updater audit

Date: 2026-10-13. Baseline: `24e2adede5e7b47506a33e6f49b459d9d61804bd`, branch `feat/panacea-brand-dashboard-20261013`. This report covers the working-tree changes in `modules/performance.py`, `modules/updater.py`, `modules/update_install.py` and their tests. Integrated GUI/build/CI evidence belongs to the coordinator's final report.

## Implemented corrections

1. **Partial Turbo restoration:** restoring a saved power change used to query unrelated settings first and report failure if an unsaved service or visual value was unknown. Restoration now skips any setting without a saved original before reading its live state. An unknown setting with a saved original still fails closed and retains its record.
2. **Recoverable Turbo state:** `get_saved_settings()` returns a tuple of persisted keys (`power`, `visual`, `SysMain`, `WSearch`, `Spooler`), an empty tuple when no originals remain, or `None` for unreadable/corrupt/locked storage. It reloads under the same process/thread transaction locks as mutations. A partial profile is not confused with lack of recovery data. The GUI owner is integrating an explicit Restore saved settings action independent of the all-settings-active switch.
3. **Interrupted installer marker creation:** a failed write/flush of a newly created exclusive readiness marker previously left an incomplete record that blocked every retry. Only a file successfully created by that write is now removed on failure; preexisting collisions remain untouched. Protected temporary JSON files also retain collision ownership checks.
4. **Rollback cleanup:** replacing the failed candidate with the original executable is now reported as a completed rollback even when deletion of the marker is locked. A later install can clean the leftover marker only when the operation metadata is valid, the backup no longer exists, and the installed PE/hash exactly matches the saved original. Pending/forged state and ambiguous identical old/new digests are preserved, never treated as proof of recovery.
5. **Interrupted HTTP protocol:** malformed HTTP status lines and incomplete reads from metadata, checksum, and executable responses are converted into `UpdateNetworkError`. Existing bounded-download cleanup still removes owned partial files.
6. **Corrected test coverage:** the previous helper-authoritative-checksum test created its workspace under a wrong parent and stopped at the target-directory check. Its fixture now reaches the real checksum comparison and explicitly verifies the SHA-256 failure message.

Each changed behavior had a failing regression before its corresponding fix. Additional tests cover failed-original retention after partial restore, recovery after app recreation, snapshot persistence failure after successful OS restoration, exclusive JSON collisions, and missing/ambiguous backup records.

## Action and failure inventory

| Action | Audited behavior / fixture evidence | Real Windows limit |
| --- | --- | --- |
| High-performance power plan | Exact original GUID persisted before mutation; readback required; custom plans restored after manager recreation; unknown current GUID prevents activation. | No host power plan changed; plan availability and actual power/thermal effect unverified. |
| Visual effects preset | Exact supported `VisualFXSetting` DWORD saved/restored, including custom value 3; unreadable/malformed registry value prevents mutation. | The backend writes a Windows preference only. It does not call `SystemParametersInfo` or modify individual animation flags. Immediate reduction of real visual effects is **not established**. GUI wording is being corrected accordingly. |
| SysMain / Windows Search / Print Spooler | Allowlisted services only; observed running/stopped state persisted; pending/unreadable state rejected; start/stop uses argument arrays with bounded command wait and follow-up state polling; an originally stopped service remains stopped on restore. | Real service changes and localized successful `sc query` output were not exercised. Read-only SysMain/WSearch probes on this host returned Access denied, demonstrating that unknown state must remain explicit. |
| Master Turbo enable | Captures all originals before any mutation; refuses any unknown original; stops activation after failure; retains all originals for recovery. Does not claim atomic OS rollback. | Actual simultaneous Windows changes require the authorized disposable environment. |
| Master / individual restore | Restores the exact recorded values, continues other restores after a failed one, retains only failed originals, and permits retry after restart or a failed recovery-record save. | No real registry/service/power mutation was performed. |
| Persistence / concurrent instances | Protected Windows handle-relative writes, flush-before-mutation, exact-state validation, named mutex serialization, stale-manager reload, and abandoned-owner recovery are exercised by isolated fixtures with mocked OS settings. | Different elevation/account combinations, real host shutdown/reboot and power-loss durability remain unverified. |
| Release discovery | Stable newer versions only; equal/older/draft/prerelease rejected; exact repo/tag and uniquely named EXE/checksum assets; bounded metadata; network failure distinct from up-to-date. | No new real release was published or downloaded by this audit. |
| Download / cancel | Exact advertised size, bounded response, SHA-256 and PE structure validation, exclusive filenames, chunk cancellation, owned partial cleanup and collision preservation. | Real CDN/network interruptions remain untested; fake response streams exercise these branches. |
| Prepare helper | Current installed image is copied as helper; staged image is independently verified; fresh PyInstaller child environment; source/manual and unprotected-install refusals preserved. | Real elevated ACL creation and packaged helper execution remain gated. |
| Replace / launch | Protected candidate verified before replacement; old image backed up; exact generated marker/token binds operation; replacement/launch failures roll back where possible; failed rollback preserves the backup path. | Replacing a running real EXE, real Windows image locks and migration from a released version were not run. |
| Readiness / finalize | Old UI must remain open until readiness; token, installed hash and original backup hash are validated; acknowledged housekeeping can retry; old helper cannot clean a newer operation's state. | Successful startup acknowledgment is not a health guarantee for later runtime. Hard termination between rename stages can leave pending recovery requiring manual inspection; no automatic arbitrary pending-state sweep is implemented. |

The SHA-256 source is the repository's HTTPS checksum asset; it is not an Authenticode signature. Automatic installation intentionally refuses user-writable Desktop/Downloads installations and leaves manual release download available. Protected helper workspaces are retained for explicit housekeeping; this audit adds no directory sweep. UI download cleanup currently removes only empty operation directories, so a verified staging EXE can remain after installation/preparation failure.

## Verification

All commands use `build/release-venv/Scripts/python.exe`. Network, launcher, registry and power/service mutation boundaries are mocked. Native file operations affect only `build/tests-*` fixture trees.

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_updater.py tests/test_update_install.py tests/test_performance.py -q --basetemp build/tests-v2-state-verified` | **124 passed**, 0 failed, 0 skipped; 4.94 seconds. |
| `python -m ruff check modules/performance.py modules/updater.py modules/update_install.py tests/test_performance.py tests/test_updater.py tests/test_update_install.py` | Passed. |
| `python -m py_compile modules/performance.py modules/updater.py modules/update_install.py tests/test_performance.py tests/test_updater.py tests/test_update_install.py` | Passed. |

Intermediate evidence is not hidden: one pre-fix run also saw `test_immediate_new_process_crash_rolls_back` fail with WinError 5 before the intended mocked crash. Immediate isolated reproduction and later scoped runs passed. A shell invocation combining pytest and a subsequent Ruff command produced 117 passes, one junction skip and five native fixture failures because retarget attempts returned WinError 5 (`test_live_attribute_retarget_cannot_create_recovery_outside[False/True]`, `test_snapshot_read_does_not_accept_retargeted_foreign_record`, `test_retarget_after_parent_validation_never_creates_an_outside_entry[False/True]`). Running the same suite through a single-command pytest invocation passed all 123 tests at that revision; the final additional ambiguity regression brings the latest result to 124 passes. No native test was disabled or weakened. Command-context permissions are a plausible explanation, not a proven OS diagnosis.

The full project suite and native GUI tests are coordinator-owned to avoid concurrent GUI work. This scoped result is not a claim that the integrated final commit, build, CI or real migration has passed.

## Independent UI review follow-up

Read-only review plus headless reproductions found a stale Turbo-refresh race: a query started before a mutation could finish after it, while the requested replacement query was rejected because the older worker still owned its group. The display then showed the old live setting alongside the newly saved recovery record. A related initial query was discarded permanently if it completed during unrelated maintenance. The coordinator implemented generation tracking and retained pending refreshes, and keeps Turbo controls disabled until the fresh result is applied.

`tests/test_ui_turbo_refresh.py` contains three deterministic real-worker regressions for those ordering/control cases. All three were observed RED before their respective coordinator fixes. Two further parameterized cases exercise the actual CustomTkinter switch/variable behavior with a Tcl-only interpreter, replacing only drawing/configuration: disabled `select()`/`deselect()` must not leave the master display stale. The coordinator uses a bound BooleanVar; the original HEAD method fails both cases when loaded into the test process, and the working-tree implementation passes. No product source file was reverted for that comparison and no Tk window was created.

The review also reproduced battery-report opener failure leaving a false Running status and callback draining scheduling another timer after queued shutdown. The coordinator's corrections preserve the saved report path with visible opener warning and stop scheduling after shutdown. Keyboard accessibility gaps in switches and the drive selector were reported to the coordinator; their native keyboard evidence remains coordinator-owned.

Latest combined focused verification: `python -m pytest tests/test_updater.py tests/test_update_install.py tests/test_performance.py tests/test_ui_turbo_refresh.py tests/test_ui_controller.py::test_battery_report_open_failure_preserves_saved_result tests/test_ui_controller.py::test_callback_drain_does_not_reschedule_after_queued_shutdown -q --basetemp build/tests-v2-state-ui-review` — **131 passed**, 0 failed, 0 skipped, 5.22 seconds. Ruff also passes for the new refresh test file. This adds five refresh cases and two corrected UI failure cases to the 124 backend tests above; it is still not the full native GUI/project suite.

## Remaining release gates

- Authorized disposable Windows environment for real Turbo activation, interruption, exact restoration and reboot behavior. No host service, registry or power settings were changed.
- Real protected-directory packaged helper creation, replacement of a running prior-release image, new-version launch/readiness, timeout/crash and failed-rollback recovery. No application executable was launched/replaced by these tests; tiny PE-shaped fixture files were never executed.
- Cross-process updater mutex contention/abandonment with actual frozen helpers, different elevation contexts and OS image locks.
- Final V2 release assets, stable download endpoint, checksum/signing identity and CI on the coordinator's final commit. No tag, release, merge, push or publication was performed by this audit.

Status: backend corrections **IMPLEMENTED**; scoped automated/isolated checks **VERIFIED**; real maintenance/migration gates **BLOCKED** pending the explicitly authorized disposable environment; **PUBLISHED: no**.

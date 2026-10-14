# Panacea V2 maintenance backend audit — 2026-10-13

Scope: `cleanup.py`, `disk.py`, `commands.py`, `operations.py`, `restore.py`, and the handle-bound primitives in `protected_files.py`, plus the narrowly delegated `performance.py` subprocess-stdin followup. The UI and Turbo owners integrate their other changes separately. This report does not attest to execution of real host maintenance.

## Action inventory and semantics

| Action / entry point | Effective operation | Result and safety contract | Verification |
| --- | --- | --- | --- |
| Temporary preview, Dashboard/Cleanup | `preview_temp_files()` visits approved user/Windows Temp roots | Read-only handle checks; `(count, bytes)` plus `last_result.skipped/errors`; locked, linked, ambiguous or redirected files are excluded | Native disposable fixtures |
| Delete temporary files | `clean_temp_files(callback)` uses the same traversal, setting file disposition through a validated handle | Counts only successful file deletions; does not recursively delete directory roots; UI owns confirmation and serialization | Native disposable fixtures; no host Temp cleanup |
| Browser caches, Resurrection | Chrome/Edge `Default` and `Profile N` `Cache`/`Code Cache`; Firefox profile `cache2` | Exact cache directories only; credentials, bookmarks and unrecognized directories preserved; invalid user-root state is partial/unverified | Native fixture profile caches; live browser caches untested |
| Empty Recycle Bin | `SHEmptyRecycleBinW(NULL, NULL, 7)` | All drives, no native prompt (UI confirms); HRESULT checked; ambiguous empty-bin error requires a successful zero-item query | Native API mocked; host bin untouched |
| Windows Disk Cleanup | Absolute System32 `cleanmgr.exe`, `shell=False` | Boolean acknowledges launch only, never maintenance completion | Launch boundary audited; executable presence read-only |
| Component store cleanup | `dism.exe /Online /Cleanup-Image /StartComponentCleanup /NoRestart` | Allowlisted direct executable, output/exit status and deadline; administrator required | Subprocess boundary mocked; actual servicing untested |
| Drive refresh | `GetLogicalDrives` + `GetDriveTypeW`, then capacity query | Only local fixed volumes; inaccessible volume retains explicit error/unknown size; no inferred SSD/HDD label | Mocked inventory/error cases plus native read-only inventory |
| Optimize selected drive | `defrag.exe <LETTER:> /O` | Exact drive-letter validation; Windows selects media-appropriate optimization; waits for exit, 2-hour failure deadline | Arguments/exit handling mocked; isolated subprocess deadline fixture |
| Windows Optimize Drives | Absolute System32 `dfrgui.exe`, `shell=False` | Boolean acknowledges launch only | Launch boundary audited; executable presence read-only |
| System file scan | `sfc.exe /scannow` | Direct executable, streamed output, exit checked; administrator required | Mocked command plus UTF-16 output fixture |
| Image health / repair | `dism.exe /Online /Cleanup-Image /CheckHealth` or `/RestoreHealth`, each with `/NoRestart` | No interactive restart; 3010 means completed with restart required; other nonzero exits fail | Mocked outcomes; actual health/repair untested |
| DNS flush | `ipconfig.exe /flushdns` | Direct allowlisted command, completion checked | Mocked; host network untouched |
| Winsock reset | `netsh.exe winsock reset` | Direct allowlisted command, completion checked; restart may be needed | Mocked; host network untouched |
| Disk health, Resurrection | `chkdsk.exe <LETTER:> /scan /perf` | Exact drive validation; no `/f` scheduling input; 0 succeeds, 1 succeeds with explicit repaired-errors message, 2/3 fail; administrator required | Allowlist/exit semantics mocked; real scan untested |
| Create restore point | Existing protection checked; `Checkpoint-Computer -RestorePointType MODIFY_SETTINGS` | A new sequence with this request's unique description must be found; throttling, unavailable query or unrelated checkpoint fails prerequisite; never enables protection implicitly | Mocked PowerShell sequence/JSON; no checkpoint created |
| Enable protection (backend-only) | `Enable-ComputerRestore -Drive <LETTER:\>` | Explicit separate action; drive grammar and exit checked | Mocked; not called implicitly or by startup |
| List restore points (backend-only) | Bounded `Get-ComputerRestorePoint`, newest first | Limit 1–100; failure logs and returns empty list; absence and query failure share this legacy return contract | Source audit; no host query needed |
| Resurrection orchestration | Strict `OperationStep` sequence and `run_sequence` | Critical checkpoint failure stops all later actions; noncritical failure yields partial; cancellation waits for current step; completed results survive presentation/cancellation-check failures | Pure integration tests; UI owner handles stage presentation |
| Protected recovery file primitives | Relative NT object opens, bound identity, exclusive file creation, flush and rename | Existing files are not reused as new snapshots; parent/object validation rejects redirection | Audited here; native snapshot tests belong to Turbo audit |

Battery report, app/settings shortcuts, administration at startup, UI double-click guards and close/navigation behavior are owned by the UI/startup audit. These modules do not elevate themselves. Missing utilities and denied privileges become launch/command failures; they are not interpreted as successful maintenance.

## Defects corrected

1. Silent subprocesses had no deadline; pipe-read exceptions could leave the child un-reaped. Both command and disk streaming now share a deadline and close the pipe/reap the direct process, reporting any unverified cleanup. Callback failure still drains the process before reporting failure. Nonzero exit codes now reach the progress/UI callback as well as the logger. Defaults are 1 hour for commands and 2 hours for optimization; timeout is an error, not a successful cancellation.
2. UTF-16LE console bytes were decoded as single-byte text and NUL-stripped, corrupting non-ASCII output. Incremental UTF-16 decoding now preserves Unicode across binary read boundaries, including a final unterminated line.
3. DISM lacked explicit restart suppression and classified reboot-required success 3010 as failure. Commands now include `/NoRestart`; successful pending reboot emits an explicit message and exposes `restart_required`, reset before each invocation.
4. `os.path.exists` enumerated remote, optical and removable roots as optimization candidates and could touch disconnected network paths. Native local fixed-drive discovery now supplies real capacity/error metadata.
5. Chromium cache cleanup ignored numbered profiles. Guarded discovery now covers supported `Profile N` paths while preserving non-cache data.
6. An unverifiable local profile could appear as a successful empty browser cleanup. It now records a skipped/unverified location.
7. Case variants of one Temp root were scanned twice, inflating preview counts. Roots are deduplicated using Windows path normalization.
8. Missing `TEMP` caused an existing known user Temp directory to be ignored. Validated user Temp is now the fallback.
9. `E_UNEXPECTED` from empty-bin deletion was treated as proof of an already empty bin. It now requires successful `SHQueryRecycleBinW` confirmation of zero items.
10. A concurrent application's newer restore checkpoint could satisfy the Resurrection prerequisite after Panacea's checkpoint was throttled. Each request now has a unique description and requires that identity plus a newer sequence.
11. Default PowerShell output encoding corrupted Unicode checkpoint descriptions. The child process now emits UTF-8 and Python decodes it explicitly. The reproduction printed `??` for `正常` before the fix; the same output-only native fixture passes after it.
12. A cancellation predicate exception discarded the sequence's completed results. It now returns a stopped partial/failed result with the original completed steps and an explicit error.
13. Independent review found that the initial timer/readline deadline implementation still blocked on a descendant holding the inherited output pipe. Streaming now uses Windows `PeekNamedPipe` (POSIX readiness polling where applicable) and only reads available bytes, with a monotonic deadline and bounded final reap. No reader thread or process-tree termination is introduced. The regression reproduced a 3.163-second return for a 0.5-second limit before the fix; independent retest returned in 0.510 seconds with descendant startup confirmed.
14. Command and disk workers expose `completion_unknown`, reset before each run, when a timeout or transport/reap failure prevents verifying normal completion. This lets the UI stop later Resurrection stages and present failed/partial outcome rather than user cancellation. Tests cover timeout/reset and pipe-error classification. A successful direct process exit does not attest to completion of unrelated system services.
15. CHKDSK exit 1 was incorrectly treated as failure despite Microsoft's definition that errors were found and fixed. It now succeeds with explicit repaired-errors feedback; exits 2 and 3 remain unsuccessful. This mapping is exclusive to CHKDSK.
16. Restore PowerShell and Turbo subprocess startup inherited invalid standard-input handles in a windowed EXE, producing `WinError 6` before launching. Both captured runners now use `stdin=DEVNULL`. Native regressions temporarily replace the test process's standard-input handle, restore it in `finally`, and execute output-only fixtures; no restore, power-plan or service API is invoked. Native sleep-process fixtures also supply explicit stdin.

UI integration findings sent to the UI owner: failed `cleanmgr`/`dfrgui` boolean launches were ignored; drive validation should consistently require the colon; Resurrection should use the actual Windows system drive; inaccessible/no-drive states should disable optimization; restart-required output should remain in persistent results; unknown command completion must stop subsequent stages and remain visible in the final result.

## Evidence

- Baseline focused suite: **57 passed in 0.43 s**.
- Initial focused suite after implementation: **82 passed in 1.16 s**, using `build/release-venv/Scripts/python.exe -m pytest -q tests/test_cleanup.py tests/test_disk.py tests/test_commands.py tests/test_operations.py tests/test_restore.py --basetemp <new workspace build/maintenance-audit-UUID>`.
- Final focused suite after independent-review fixes: **121 passed in 7.50 s**, using the same command with `tests/test_performance.py` added and a fresh `build/maintenance-final-UUID` fixture root. This comprises 90 maintenance tests and 31 Turbo tests; it is not the full application suite. Scoped Ruff and `git diff --check` passed again.
- Independent reviewer reran the original three reproductions: inherited output pipe deadline **0.510 s** for **0.5 s**; CHKDSK exit 1 returned success with repaired-errors feedback; output-only PowerShell succeeded with an invalid inherited stdin handle. The independently run maintenance suite passed **90 tests**.
- Each corrected failure was reproduced before its implementation. New tests include native disposable NTFS files, a child Python sleep process for silent deadlines, output-only PowerShell Unicode, and mocked maintenance APIs.
- The tool sandbox changed during the audit: an intermediate run produced **46 passed / 36 fixture-setup errors** from its inaccessible default Temp root. A workspace fixture root resolved that condition, then produced **72 passed / 2 skipped / 8 failures** because the sandbox denied existing hardlink, reparse and case-sensitivity fixture operations. Tests were not weakened. The same 82 tests passed outside the tool sandbox, with fixtures confined to a new UUID directory under the workspace.
- Scoped Ruff: **All checks passed**. Scoped `git diff --check`: passed.
- Read-only native drive enumeration returned one available local fixed volume, `C:`, and capacity values. The following resolved absolute system executables existed: `cleanmgr`, `dfrgui`, `defrag`, `sfc`, `dism`, `ipconfig`, `netsh`, `chkdsk`, `powershell`. Existence is not a successful maintenance execution.
- Full-suite/native GUI/EXE checks are coordinated by the root agent and are not included in this focused result.

## Remaining release gates

- A separately authorized disposable Windows environment is still required for real cleanup against live browser profiles, Recycle Bin, SFC/DISM/CHKDSK/defrag, restore protection/checkpoint throttling and complete Resurrection execution, including reboot-required and interrupted states.
- Native process deadline fixtures verify bounded return, closure of the output pipe and termination/reaping of the direct launched process, including a descendant retaining its output handle. The finite fixture descendant exits naturally. Real Windows maintenance may use services or child processes; their completion is unknown after timeout, and no process-tree cleanup or end-to-end recovery is asserted without the disposable environment.
- Cancellation is deliberately between steps; it neither undoes completed actions nor claims rollback. System Restore is a prerequisite checkpoint, not proof of successful rollback or recovery of permanently deleted personal files.
- UI persistence, accessibility, screenshots and release build/CI status are documented by the coordinating audit.

## Primary API references

- [SHEmptyRecycleBinW](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shemptyrecyclebinw): S_OK is success; other HRESULTs are errors.
- [DISM global options](https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/dism-global-options-for-command-line-syntax?view=windows-11): `/NoRestart` suppresses restart prompts/automatic restart.
- [Windows system error codes 1700–3999](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--1700-3999-): 3010 is successful completion requiring reboot.
- [CHKDSK exit codes](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/chkdsk#understanding-exit-codes): exit 1 means errors found and fixed; exit 2 is ambiguous and exit 3 indicates checking/repair failure.

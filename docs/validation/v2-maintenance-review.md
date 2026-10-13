# Independent V2 maintenance review

Review date: 2026-10-13. Compared maintenance changes against `24e2ade` in
`modules/cleanup.py`, `commands.py`, `disk.py`, `restore.py`, `operations.py`
and their tests. Reviewer did not edit those implementation/test files.
Follow-up scope includes the new durable `modules/maintenance_guard.py`, its
tests, and UI completion/sequence integration in `panacea_ui.py`.

## Findings and remediation

### MR-1 — P2: inherited output pipes bypass the stream deadline

Location at review: `modules/commands.py`, `run_process_stream`, timer callback
and blocking `stdout.readline()` loop (lines 44–60 before remediation).

The deadline kills only the direct child. A descendant retaining the inherited
stdout handle keeps the read blocked, even after the direct child is killed.
The timeout is checked only after EOF, so it cannot bound this case. A stuck
helper can retain the maintenance lock past the configured deadline.

Verified with a safe Python parent/descendant fixture, without maintenance APIs:

```python
script = (
    "import subprocess,sys,time; "
    "subprocess.Popen([sys.executable,'-c','import time; time.sleep(3)'], "
    "stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr); "
    "print('owned descendant started',flush=True); time.sleep(30)"
)
run_process_stream([sys.executable, '-c', script], print, timeout=0.5)
```

The readiness message appeared before the deadline; `TimeoutExpired` returned
after **3.177 seconds**. The descendant was deliberately finite and exited
itself. A 0.1-second variant was too short to guarantee descendant creation and
was discarded as evidence. Requested remediation: enforce the deadline while
draining the pipe, independently of direct-child liveness, with a regression
for inherited handles. Avoid killing unrelated operating-system processes.

**Resolved and independently retested.** The owner replaced the timer/blocking
read with available-byte polling (`PeekNamedPipe` on Windows, `select` on POSIX),
with the monotonic deadline checked in the same loop. Output buffering is
bounded; the direct child is reaped, and no daemon reader or OS-wide process-tree
termination is used. The original fixture now returns `TimeoutExpired` after
**0.510 seconds**, having emitted the descendant-readiness message. Its finite
descendant was allowed to exit naturally. Transport and cleanup uncertainty is
surfaced through `ProcessCompletionUnknown`; command and disk managers expose
`completion_unknown` for both that exception and `TimeoutExpired`.

### MR-2 — P2: CHKDSK repair success is reported as failure

Location at review: `CommandRunner.run_command_stream`, generic nonzero exit
branch (approximately line 138 before remediation). This is a retained
pre-existing semantic gap discovered during the broader functional audit.

CHKDSK exit code 1 means errors were found and fixed, according to Microsoft's
[exit-code documentation](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/chkdsk#understanding-exit-codes).
The current generic branch returns `False`, prints a failure, and marks the
Resurrection step unsuccessful. An injected stream result of 1 for the
allowlisted `chkdsk C: /scan /perf` command reproduced:

```text
result: False
feedback: Disk health scan failed with exit code 1.
```

Requested remediation: interpret code 1 as repaired/completed for CHKDSK only,
with explicit repair feedback; retain caution for ambiguous code 2 and failure
for code 3. This fixture did not execute CHKDSK or alter a volume.

**Resolved and independently retested.** CHKDSK code 1 now returns `True` with
the explicit feedback `errors repaired`; code 2 and code 3 remain unsuccessful.
The special handling applies only to CHKDSK. DISM code 3010 retains its separate
restart-required result.

### MR-3 — P1: invalid inherited stdin prevents restore queries from starting

Location at review: `RestoreManager._run_powershell`, subprocess launch
(lines 16–22 before remediation). This is a retained pre-existing subprocess
gap that also affects the updated restore-verification path.

The runner redirects stdout/stderr but leaves stdin inherited. A process
launched with an invalid standard-input handle can fail in `Popen` with
`WinError 6` before PowerShell starts. Restore listing/creation then become
unavailable, and Resurrection cannot pass its mandatory checkpoint.

Deterministic safe reproduction inside a fixture Python process:

1. Save the current `GetStdHandle(DWORD(-10))` result.
2. Set only that fixture process's stdin with
   `SetStdHandle(DWORD(-10), HANDLE(-1))`.
3. Call `_run_powershell("Write-Output 'fixture-only'", timeout=5)`.
4. Restore the original handle in `finally`.

Observed `OSError(9, 'Handle non valido', None, 6, None)`. No restore cmdlet,
service change or registry write was executed. Requested remediation:
`stdin=subprocess.DEVNULL`, matching the maintenance/monitor runners, and an
invalid-stdin fixture regression. This is conditional on the launching process's
standard-handle state; it does not imply every windowed launch fails.

**Resolved and independently retested.** Restore PowerShell launches explicitly
use `stdin=subprocess.DEVNULL`. The same process-local invalid-stdin fixture now
returns exit code 0 and `fixture-only`, without calling Windows restore APIs.
The owner also corrected the native timeout test harness to use explicit stdin.

### MR-4 — P2: the timeout maintenance lock clears when the app is reopened

Location: `PanaceaApp._request_operation` and `_maintenance_uncertain` state.

After an unverified command completion, the initial UI correctly disabled
maintenance and asked the user to restart Windows. The flag existed only in
memory, however: closing and reopening Panacea cleared it even if the possibly
surviving Windows helper was still running. This conflicted with consistency
after reopening and permitted another operation before the stated restart
prerequisite. Requested remediation: persist the uncertain state against the
Windows boot session, retaining it until a reboot is verified.

**Resolved and independently retested, including final UI integration.** The new
`MaintenanceGuard` stores protected immutable records tied to the documented
Windows successful-boot counter (see MR-5). Reopening on the same boot remains
blocked. Only a strictly newer counter can make intact records obsolete.
Missing boot identity, malformed records, query failure and an interrupted
write remain blocked.

The constructor reads the guard before building controls and shows its reason
before the window becomes visible. `_request_operation` persists uncertainty
from the worker's `finally` block before result/error delivery, including an
exception raised after a timeout. Independent headless fixtures confirmed that
the write runs outside the UI thread, the maintenance group remains occupied
until delivery, and both result paths disable further maintenance. The exact
guard reason remains in the status and blocked-action feedback. A failed save
retains the session lock and visibly reports that persistence failed.

An additional interruption edge was found during this review: directory
creation could succeed before record creation failed. An existing empty guard
directory originally appeared clear on reopening. The owner reproduced this
case and corrected it to fail closed; the final independent run includes both
the empty-directory and interrupted-before-file regressions.

The guard performs no startup write when storage is absent. If all storage
creation is denied, it cannot promise persistence; `mark_unknown()` returns
`False`, retains the in-memory block and supplies a specific error. This is an
explicit limit, not proof of durable recovery. Unknown-boot/corrupt records do
not automatically clear after a reboot, because that reboot cannot be verified
against the original state.

### MR-5 — P2: a changed WMI timestamp is insufficient proof of a reboot

Final primary-source checking found that the guard's selected boot signal has a
documented instability. Boost Interprocess's maintainers removed WMI
`LastBootupTime` for boot/session identity after finding it unstable with time
synchronization and hibernation. Its current release-history documentation
continues to classify the old behavior as broken. See the Boost 1.54 and 1.74
sections of the [official Boost release notes](https://www.boost.org/latest/doc/html/interprocess/acknowledgements_notes.html).

The initial guard unlocked after *any* different valid timestamp. UTC
normalization handles timezone representation but cannot distinguish a changed
timestamp from an actual reboot. This is direct historical primary evidence,
not an independently reproduced current-Windows bypass; the reviewer did not
alter the host's clock, power state or boot. Requested remediation: use a stable
boot-session identifier or retain the block unless an actual reboot can be
verified.

**Resolved and independently retested.** The provider now reads the `REG_DWORD`
`BootId` value under `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management\PrefetchParameters`
using read-only registry access. Microsoft documents this counter as incremented
on each successful boot in its [memory-integrity documentation](https://learn.microsoft.com/en-us/windows-hardware/design/device-experiences/oem-hvci-enablement#recommended-configuration).
The guard requires a strictly greater counter than every saved record before
allowing maintenance. Counter rollback or wrap remains blocked conservatively.
There is no WMI timestamp or uptime fallback; legacy timestamp records cannot
automatically clear the guard. The native boot-environment GUID candidate was
rejected because it identifies a boot/BCD entry rather than proving a new
session. No reboot or host clock/registry mutation was performed.

## Other reviewed behavior

- Browser profile expansion remains restricted to the known local cache roots,
  Default and numbered Chromium profiles; guarded ancestors are revalidated
  again when each returned cache path is processed. No new unguarded deletion
  boundary was found in the profile-discovery change.
- Recycling `E_UNEXPECTED` now requires a successful empty-bin query before
  reporting success, replacing the unsupported assumption that this error
  always means the bin was already empty.
- Restore verification binds a newer sequence number to the exact per-request
  UUID description, preventing a concurrent installer's unrelated point from
  satisfying the checkpoint. Errors and unavailable queries remain fail-closed.
- The configured restore-point creation throttling is not bypassed. Microsoft
  documents the client-only support and daily restriction for
  [`Checkpoint-Computer`](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.management/checkpoint-computer?view=powershell-5.1).
- `/O` asks Windows to choose optimization for the media, as documented for
  [`defrag`](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/defrag).
  Reporting the discovered drives as `Fixed` avoids guessing SSD/HDD.
- Cancellation/progress errors in `run_sequence` stop further steps and retain
  completed step results. A failed critical restore step prevents cleanup.
- The UI's unknown-completion integration stops Resurrection before the next
  step, retains attempted results and reports `partial` rather than claiming a
  user cancellation. Ordinary user cancellation still preserves completed
  steps and marks the remaining steps `not run`.
- A headless integration fixture exercised real worker completion delivery,
  then drive/Turbo/saved-state refreshes, then another maintenance request.
  The lock was set before completion handling re-enabled controls; all affected
  controls stayed disabled and the subsequent work callback was never invoked.
- The final component-store cleanup routing sends its start, command output and
  completion line to the Cleanup details log. `run_cmd` retains the Tools log
  by default; the optional log callback does not change confirmation, command
  validation, serialization or result handling.

## Verification limits and follow-up

Findings were sent promptly to the coordinating agent and maintenance owner.
Pre-remediation observations above are retained to distinguish reproduced bugs
from subsequent verification.

An independent focused run of cleanup, commands, disk, restore and sequence tests
produced **86 passed, 1 failed** before remediation. The failing
`test_silent_maintenance_process_times_out_and_is_reaped[disk]` never populated
its `children` list: its native fixture launch also inherited stdin instead of
using `DEVNULL`, exposing the same invalid-handle harness condition described
in MR-3. This was reported to the owner and the harness was fixed.

Fresh independent command:

```text
python -m pytest tests/test_cleanup.py tests/test_commands.py tests/test_disk.py tests/test_restore.py tests/test_operations.py tests/test_ui_controller.py -k "not real_tk" -q --tb=short --basetemp build/maintenance-ui-independent-final
```

Result: **127 passed, 6 deselected** in 5.68 seconds. The deselected tests use
native Tk and were intentionally left to the coordinating agent to avoid GUI
interference. Scoped `git diff --check` also passed.

Independent durable-guard follow-up:

```text
python -m pytest tests/test_maintenance_guard.py tests/test_performance.py -q --tb=short --basetemp build/guard-independent-first
```

Result: **49 passed** in 2.99 seconds (18 guard and 31 performance tests),
including the final interrupted-before-record regression. Link/reparse tests
used only private fixture paths. No real Panacea recovery marker was created.

Final backend retest after the BootId correction:

```text
python -m pytest tests/test_maintenance_guard.py tests/test_cleanup.py tests/test_commands.py tests/test_disk.py tests/test_restore.py tests/test_operations.py tests/test_performance.py tests/test_ui_controller.py -k "not real_tk" -q --tb=short --basetemp build/maintenance-guard-review-authorized-20261013
```

Result: **179 passed, 6 deselected** in 9.03 seconds. The first attempt under
the tool sandbox had 161 passed, 15 failed and 3 skipped: its NTFS hardlink,
reparse and case-sensitivity fixture controls were denied with `WinError 5`.
The unchanged suite passed outside that sandbox, with native fixture operations
confined to the uniquely named workspace test directory. Tests were not weakened.

Final UI integration retest:

```text
python -m pytest tests/test_ui_controller.py tests/test_ui_turbo_refresh.py -k "not real_tk" -q --tb=short --basetemp build/mr4-ui-independent-final
```

Result: **46 passed, 6 deselected** in 0.69 seconds. This includes all three
new timeout-guard cases: normal result, error after timeout, and persistence
failure. A separate headless thread-identity fixture verified that persistence
precedes delivery on a worker thread and that exact guard reasons survive both
normal/error callbacks and a rejected subsequent request. Constructor ordering
was reviewed directly; no native GUI was launched by this reviewer.

No native GUI, actual cleanup, restore point, DISM, SFC, network reset or drive
optimization was executed by this reviewer. The native subprocess reproductions
only launched owned finite Python fixtures or attempted a literal PowerShell
output command. Live Windows maintenance remains a separate disposable-system
release gate.

Remediation status: **MR-1 through MR-5 resolved and independently verified.
No remaining actionable finding in the reviewed scope.** The explicit storage
failure limitation and disposable-Windows release gate remain as stated above.

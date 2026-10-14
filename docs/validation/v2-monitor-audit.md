# V2 system monitor and Windows Update audit

Validated locally on 2026-10-13. Scope: `modules/system_monitor.py`, its tests,
and the nullable Dashboard data contract coordinated with the UI owner.

## Implemented and verified

| Area | Reproduced defect | Corrected behavior |
| --- | --- | --- |
| RAM usage | A failed `GlobalMemoryStatusEx` call could expose stale output or a fabricated 0%; zero capacity and free > total were accepted. | Check the API success result and capacity bounds; return `None` when unavailable. |
| CPU usage | Failed `GetSystemTimes`, an initial sample, zero elapsed time or impossible counter deltas could report a valid 0%, 110% or -900%. | Require successful native reads and a valid elapsed interval; failed reads retain the previous valid baseline. Unavailable samples return `None`. |
| CPU on large systems | `GetSystemTimes` covers one processor group on systems with multiple groups. | Return unavailable when multiple groups are active instead of presenting a partial measurement as whole-system usage. |
| System disk | Capacity and disk model always targeted C:. | Resolve the actual Windows system volume through the native system-directory resolver; both capacity and model use that validated drive. No environment/PATH command fallback. |
| Disk availability | Failed reads and impossible capacity values returned healthy zero usage. | Return `None` for unavailable or invalid capacity. |
| RAM metadata | Rated `Speed` was presented as the configured clock; the first module described every module; unknown memory type was invented as DDR. | Query `ConfiguredClockSpeed`, evaluate all modules, identify mixed types/speeds, preserve unknown values. |
| CPU metadata | An exception reading frequency left an opened registry handle unclosed. | Close the owned registry handle in `finally`. |
| Windows Update emptiness | Empty output returned `(0, 0, 'Unknown')`, allowing a green UI status. | Empty/malformed/invalid output returns `(-1, -1, status)`. Only a confirmed successful empty search reports `No available updates`. |
| Windows Update completeness | Counts lacked a WUA operation result, so partial search results were indistinguishable from success. | Use structured JSON; require `ResultCode == 2` and nonnegative integer counts. Partial/failed/cancelled results remain unavailable. |
| Windows Update classification | `AutoSelectOnWebSites` was incorrectly labelled mandatory/security-critical. | Classify optional updates using `BrowseOnly`; describe the other available updates as recommended, never mandatory. |
| Windows Update filtering | Installed-only filtering could count hidden updates. | Query `IsInstalled=0 and IsHidden=0`; also exclude hidden/installed entries before counting. |
| Query encoding/errors | Localized output could fail UTF-8 decoding and PowerShell nonterminating errors could continue. | Metadata/update scripts explicitly emit UTF-8 and stop on errors. Windows Update also uses strict property handling. |

The existing owned-process lifecycle remains intact: trusted executable paths,
`shell=False`, `stdin=DEVNULL`, bounded timeouts, off-UI-thread cancellation,
owned-child reaping and pipe closure. Existing lifecycle regressions still pass.

## Data contract

`sample_fast()` retains `cpu`, `ram`, `disk`, `uptime`, and `battery`, and adds
`system_drive` (e.g. `D:`, or `None`). CPU is a float or `None`; RAM/disk are
their original three-value tuples or `None`. Missing readings must display as
unavailable and must not add synthetic zero samples to graphs.

`get_windows_update_status()` retains a three-value tuple:
`(recommended_count, optional_count, status)`. Counts are `-1, -1` when a search
cannot be verified. Positive optional-only results still indicate updates are
available. Zero counts mean a successful search found no applicable visible
updates in the configured Windows Update source; they are not a broader claim
about installed updates, security posture or pending reboot status.

## Evidence

Regression tests were run against the old implementation before fixes:
19 initial failing cases reproduced false metric values, C: selection and
incorrect/empty update results. A second test pass reproduced the RAM metadata,
registry-handle and processor-group defects before those fixes.

- `python -m pytest tests/test_system_monitor.py tests/test_ui_icons.py -q --tb=short --basetemp build/monitor-icons-final`:
  **132 passed** (56 monitor tests and 76 icon tests).
- `python -m pytest tests/test_ui_controller.py tests/test_system_monitor.py tests/test_ui_icons.py -q -k 'not real_tk' --tb=short --basetemp build/monitor-ui-integration`:
  **161 passed, 6 deselected**. Native Tk cases were intentionally left to the
  main GUI verification owner to avoid concurrent desktop interaction.
- Four actual PowerShell fixture executions cover: a confirmed empty update
  search; non-optional/optional classification with deliberately contradictory
  `AutoSelectOnWebSites`, hidden and installed entries; D: disk selection; and
  configured RAM clock projection. Fixture functions replace COM/CIM/storage
  providers inside the child process. No host Windows Update search, install,
  registry write, service modification or disk maintenance is executed.
- The existing native sleeping-child fixtures verify cancellation/timeout and
  handle cleanup on isolated test processes.
- A separate native read-only `sample_fast()` check produced available CPU,
  RAM, disk, resolved system volume and uptime; CPU was within 0–100%.
- `git diff --check -- modules/system_monitor.py tests/test_system_monitor.py`:
  no whitespace errors in this audit's changes.

A Windows test-harness issue was also resolved: inherited stdin can be an
invalid handle in a noninteractive runner. The new PowerShell fixtures now use
`stdin=DEVNULL`, matching the production query runner. No test was disabled or
weakened to conceal that failure.

## Sources and limits

Microsoft documents the Boolean success results of
[`GlobalMemoryStatusEx`](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-globalmemorystatusex)
and [`GetSystemTimes`](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getsystemtimes),
including kernel time's idle component and the processor-group limitation.
[`Win32_PhysicalMemory`](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-physicalmemory)
defines the configured clock property and its unknown value.

The official
[`IUpdateSearcher::Search`](https://learn.microsoft.com/en-us/windows/win32/api/wuapi/nf-wuapi-iupdatesearcher-search)
documentation defines `BrowseOnly` and `IsHidden`;
[`AutoSelectOnWebSites`](https://learn.microsoft.com/en-us/windows/win32/api/wuapi/nf-wuapi-iupdate-get_autoselectonwebsites)
describes automatic selection, not severity or mandatory status.
[`OperationResultCode`](https://learn.microsoft.com/en-us/windows/win32/api/wuapi/ne-wuapi-operationresultcode)
distinguishes success from success with incomplete results.

Not verified here: live WUA service/network/WSUS behavior, actual multi-group
hardware, physical non-C: Windows installation, effective Windows DPI or final
EXE UI. Fixture evidence proves the tested data/command semantics, not success
of those external environments. Multi-group aggregate CPU is explicitly
unsupported and shown as unavailable; all other metrics remain independent.

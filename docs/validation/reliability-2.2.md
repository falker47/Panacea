# Reliability validation for Panacea 2.2

The Qt recovery banner explains why maintenance is blocked. Operation history also provides access to diagnostics when the guard is clear. T4 exports `reliabilityService` and `historyService` from `qt_app.bridges.reliability_bridge.create(app_context)`. T3 registers them before loading QML. Fixture smoke mode keeps both services in memory.

## Guard decisions

`ReadService.collect("guard_status")` retains `blocked` and `message`. The additional fields are `code`, `since` (UTC evidence timestamp), `action_id`, `resolution` and `safe_to_clear`. Missing evidence is represented by a null timestamp or action. Read-only status takes a zero-wait lease and creates no files. A new Qt operation can attach its action ID to the existing v1 pending journal through a separate advisory record. File identity and creation time must match before Panacea displays that ID.

| Code | What the user can do |
| --- | --- |
| `clear` | Start a confirmed operation. |
| `busy_other_instance` | Wait for the owner to finish, then verify again. Recovery takes the same machine-wide mutex with zero timeout. |
| `unknown_completion_same_boot` | Restart Windows. A known timeout on the current boot prevents manual archiving. |
| `unknown_completion_previous_boot` | Verify again. A strictly greater Windows BootId proves the old records can be retired. An in-process timeout latch is released only after this check. |
| `interrupted_journal` | Verify after restarting Windows. If the records still block work, review the risk and confirm archiving. |
| `unverifiable_storage` | Check access to Panacea’s data and verify again. Explicit archiving is available when the storage objects can be safely opened and moved. A missing boot identity or a counter rollback cannot prove a restart. |

**Archive and unblock** consumes a service-owned, one-use nonce. The service rechecks the reviewed state under the maintenance mutex. It moves the guard, journal and any operation label into `maintenance-recovery-pending` by handle, writes the confirmation to the operation history, then renames the staging folder to `maintenance-archive-<UTC timestamp>-<suffix>` beside the original directories. This last rename releases the persistent block. A sharing, permission or audit failure leaves the records available for another attempt. The history outcome `confirmed` records the user’s decision before that final rename. Successful verification after a proven reboot also retains the evidence in an archive.

A prior Windows command may still be active after an interruption. Archiving changes Panacea’s state. Only the user can decide whether to accept the risk of running maintenance again. The normal Windows action gateway still requires preparation, confirmation, a one-use nonce and a journaled lease.

## Local files and diagnostic privacy

The logger, crash capture, history and export resolve Windows Known Folders through the Shell. The previous log remains at `Documents\SystemOptimizer\log.txt`. Panacea leaves that file in place and starts a new UTF-8 log under LocalAppData. [Microsoft Known Folder API](https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath)

| Location | Contents and retention |
| --- | --- |
| `LocalAppData\Panacea\logs\panacea.log` | Application and Qt warnings. Rotation uses five 1 MiB backups. |
| `LocalAppData\Panacea\logs\crash-marker.log` | Python exception notices and native faulthandler output. The Python traceback goes to the application log. Dismissing the banner acknowledges the byte position seen at startup, preserving a later crash notice. |
| `LocalAppData\Panacea\history.jsonl` | One typed record for each confirmed execution reaching the gateway, including failures and cancellations. Appends are serialized and flushed to disk. The next append after 2,000 lines rotates the file to `history.1.jsonl`. Reads page across both generations and count corrupt lines. |
| `Downloads\Panacea-diagnostics-<UTC timestamp>.zip` | The preview lists all six members. A successful export selects the ZIP in Explorer. The file stays in Downloads if Explorer cannot open. |

The ZIP has a 4 MiB limit on both the uncompressed payload and the finished archive. It reads only the current Panacea log and its five rotations, with a shared 2 MiB input budget, and up to 100 recent history records. Log output is projected to time, severity and recognized event categories. Free-form command output, paths and tracebacks remain local.

| ZIP member | Exported fields |
| --- | --- |
| `system.json` | App version, Windows build, crash category and history read status. |
| `guard.json` | Recovery code, resolution, safe-to-clear and blocked flags, time and recognized action. |
| `logs.txt` | Privacy-filtered application and Qt events in chronological order. |
| `history.jsonl` | Schema-checked operation IDs, times, action, outcome, metrics, restart flag, error code and version. |
| `update-readiness.json` | Marker availability and the boolean `protected` and `ready` fields when present. |
| `settings.json` | Resolved language, language choice and supported boolean preferences. |

## Regression evidence

The Windows fixture suite exercises all six guard states, two independent processes contending for the maintenance mutex, interrupted archiving, mandatory audit writes and byte-for-byte preservation of damaged records. History tests cover concurrent writers, the 2,000-line boundary, malformed JSON, partial writes and failures in the maintenance finally block. Diagnostics tests include decoy secrets, a fake executable, hard links, a directory junction, bounded log tails and a mocked Explorer launch.

Qt tests load both feature files with fake services in Italian and English. They exercise keyboard confirmation, the ZIP preview, status filtering, operation details and crash dismissal. The tests check accessible names, roles, visible font sizes and Qt warnings. Real maintenance actions, installed-client transactions and installer probes belong on disposable hosted runners.

On the same-repository Draft PR, verify the checkout SHA in the job summaries. In `ci.yml`, `windows-smoke` covers the Python/Qt suites, one-file build, import smoke, installer and performance budgets. `windows-isolated-integration` covers native fixtures and packaged replacement. `windows-installer-integration` covers protected installation, update, rollback and uninstall. In `update-compat.yml`, require `linux-contract`, `build-candidate`, `transport-canary`, all five `client-acceptance` rows, all five `native-install` rows and `client-summary`. The protected startup budget is 15 seconds. The executable and extracted-size limits are 70,000,000 and 180,000,000 bytes. [Published-client matrix](update-compat.md)

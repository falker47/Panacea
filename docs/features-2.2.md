# Health, startup, cleanup and storage in Panacea 2.2

The four views run when requested. Startup changes and cleanup use the shell’s confirmation dialog. Confirmation is single-use. Inside the maintenance lease, Panacea reads the selection again before it changes Windows. If the source, approval value or eligible file inventory changed, refresh the view and confirm a new selection.

## Health check

The score starts at 100. Each observed condition below deducts its weight once. The view shows the evidence, deduction and an action for reviewing the finding. A partial check shows a range. The upper end subtracts confirmed deductions. The lower end also subtracts weights that missing evidence could still affect. With no readings the range is 0–100. The thresholds describe observed maintenance conditions.

| Evidence | Deduct when | Points | Where to review |
| --- | --- | ---: | --- |
| Free and total logical bytes on the Windows system drive | Below 10% free | 25 | Storage analysis |
| CBS RebootPending, Windows Update RebootRequired, PendingFileRenameOperations | At least one indicator is present or the pending rename list contains a path | 15 | Windows Update and restart options |
| Windows tick count since boot | At least 7 full days | 5 | Windows Update and restart options |
| Existing Windows Update query | At least one recommended update. Optional updates are displayed separately | 15 | Windows Update |
| System volume GUID in the System Restore SPP client’s registered volumes | Policy disables System Restore or the readable list excludes the system drive | 10 | System Protection and restore options |
| Enabled items across the five startup sources | At least 10 observed | 10 | Startup apps |
| Eligible Temp and deep-cleanup logical bytes | At least 1 GiB observed | 10 | Deep cleanup and Temp preview |
| Windows shell’s Recycle Bin size | At least 512 MiB | 5 | Recycle Bin in Cleanup |
| Maintenance guard | The existing guard reports a block | 5 | Maintenance history |

The reclaimable estimate adds the Temp preview, WER reports, thumbnail/icon caches and the shader cache. Temp can already contain Panacea downloads. Opt-in crash dumps and Windows-managed Delivery Optimization totals do not enter the sum. Locked files and unreadable locations can reduce coverage. An inaccessible protection list, update count or guard status is unknown. A restore point’s existence is insufficient to establish current protection. Enabling System Protection or restarting Windows remains a user decision.

## Startup apps

Panacea reads the following sources. Each row shows the scope, command or shortcut, approval state and any available change time. Locally resolved executables may supply a company name and description from version resources. These strings are publisher-supplied metadata, without signature verification.

| Scope | Startup source | Explorer approval subkey |
| --- | --- | --- |
| Current user | `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` | `HKCU …\StartupApproved\Run` |
| Machine | `HKLM\Software\Microsoft\Windows\CurrentVersion\Run`, native view | `HKLM …\StartupApproved\Run` |
| Machine, 32-bit apps | `HKLM\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run` | `HKLM …\StartupApproved\Run32` |
| Current user | Startup Known Folder, normally `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` | `HKCU …\StartupApproved\StartupFolder` |
| All users | Common Startup Known Folder, normally `%ProgramData%\Microsoft\Windows\Start Menu\Programs\Startup` | `HKLM …\StartupApproved\StartupFolder` |

The approval prefix is `Software\Microsoft\Windows\CurrentVersion\Explorer`. Missing approval means the entry is enabled by default. Panacea recognizes the 12-byte Explorer record with enabled codes 02/06 and disabled code 03. A nonzero FILETIME is shown in UTC. Unrecognized records stay untouched. An item’s ID is derived from scope, source and entry name.

Disable writes the disabled code and current FILETIME to the approval value. Enable writes the normal enabled code and clears the disable time. This restores sign-in behavior while leaving the original Run value or shortcut in place. The change takes effect at a future sign-in. Running processes, services, scheduled tasks and other startup mechanisms are outside this view. [Microsoft’s startup settings and source locations](https://support.microsoft.com/en-us/windows/experience/startup-boot/configure-startup-applications-in-windows)

## Deep cleanup

Preview lists eligible file counts, logical bytes, up to five example paths and the number of skipped entries. The Windows file-handle checks refuse reparse points, multiply linked files and unverifiable identities. A locked file can remain after cleanup. The result reports each category separately. File deletion bypasses the Recycle Bin and is irreversible. Logical bytes can differ from the resulting change in free space.

| Category | Eligible locations |
| --- | --- |
| Windows error reports | ReportArchive and ReportQueue beneath `Microsoft\Windows\WER` in the ProgramData and LocalAppData Known Folders |
| Thumbnail and icon caches | Files matching `thumbcache_*.db` or `iconcache_*.db` directly under `%LOCALAPPDATA%\Microsoft\Windows\Explorer` |
| DirectX shader cache | File contents beneath `%LOCALAPPDATA%\D3DSCache` |
| Delivery Optimization | Windows supplies Files and CacheSizeBytes through `Get-DeliveryOptimizationPerfSnap`. The official `Delete-DeliveryOptimizationCache -Force` command manages eligible cached data. Windows keeps pinned files. Physical sample paths and exact deleted bytes are unavailable for this category |
| Crash dumps | `%WINDIR%\Minidump\*.dmp`, `%WINDIR%\MEMORY.DMP` and `%LOCALAPPDATA%\CrashDumps\*.dmp`. **Unchecked by default.** Keep the dumps when investigating a crash |
| Stale Panacea downloads | Direct children of `%TEMP%` named `Panacea-Qt-update-*` with directory modification time older than 24 hours. Panacea removes its `Panacea-*.part` and `Panacea-*.exe` downloads directly inside, then removes the directory only if empty |

The approval covers the previewed files. The removal pass checks identity again on the open handle. Unrelated contents, helper workspaces beside the installed executable, backups and readiness markers stay in place. An unavailable Delivery Optimization probe is reported separately. The Windows Update download folder `%WINDIR%\SoftwareDistribution\Download` is outside the selection. Use the existing DISM component cleanup or Windows Disk Cleanup to review Windows servicing files. [Microsoft’s Delivery Optimization counters and cache command](https://learn.microsoft.com/en-us/windows/deployment/do/waas-delivery-optimization-monitor)

## Storage analysis

Choose the user profile or a local fixed drive. Panacea walks directory entries without following reparse points and reads file metadata. Scanning stops at cancellation, 100,000 entries or 15 seconds, checked between filesystem calls. A pending Windows call can delay a stop. The view displays progress, unreadable entries and whether a result is partial.

The largest 20 folders include logical file bytes from their descendants and are grouped through three directory levels. Parent and child rows overlap. Adding the displayed folder sizes would count some bytes twice. The largest 50 files are ranked at or above 100 MB (100,000,000 bytes). Sizes shown in MiB or GiB use binary units. Hard-linked names can contribute more than once to logical totals.

Scan reuses the result for a location during this session. Rescan reads the location again. Open in Explorer selects an item from the scan after checking the path. The storage view has no deletion control.

## Privacy

The inventories, sample paths, startup commands and scan cache are held in application memory. They are visible to anyone viewing the window. The features do not upload them or save an inventory report. The existing Windows Update query can contact the update service configured on the PC. Confirmed maintenance uses Panacea’s existing guard journal and the command runner can log the command’s outcome. Windows manages its own event and service records.

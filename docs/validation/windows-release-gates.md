# Windows release gate protocol

Status: pending an explicitly authorized disposable Windows environment. Do not run sensitive operations or the published legacy EXE on the user's host. Retain an independent VM snapshot/backup and isolate any test-only network interception and trust changes to that VM. Approval of the VM tests is separate from final stable-publication approval.

Candidate identity is in candidate-package.json; production CI artifact may use Python3.12 and have a different checksum. Test the exact eventual release bytes and record their digest, immutable source commit and job URL. Published v1.47 was downloaded and verified (zero-latest-baseline.json); it has not been executed here.

| Gate | Procedure/evidence required | Current evidence |
| --- | --- | --- |
| Interactive startup/UAC | Start actual EXE normally from paths with spaces/Unicode; accept and decline elevation; verify new extraction, application version and errors | Quoting/reset unit tests and new safe EXE startup only |
| DPI/layout | Actual Windows display scaling100/125/150%,1366x768 and1920x1080; all seven views, keyboard navigation/focus, resize and dialogs |42 source screenshots at CTk widget scales; actual OS change not run |
| Dashboard/lifecycle | Readable CPU/RAM/disk, eventual hardware metadata/update state; navigate during sampling; close/reopen; offline error/retry | Native screenshots, source/EXE probes, controller tests |
| Cleanup | In VM only, controlled temp/cache fixtures, preview, locked files, reparse/hardlink sentinel, totals and partial feedback | Native temporary-fixture tests passed on host; broader VM/manual gate pending |
| Turbo | Record genuine original plan/services/visual value, change individual/master controls, restart then restore exact original; verify save failure blocks mutation | All OS settings mocked; native persistence/mutex fixtures passed |
| Restore/Resurrection | With explicit VM permission for repairs, verify true restore sequence; stop on unavailable/throttled restore; per-step status and cancellation between steps | Mocked command/restore/sequence tests only |
| Old-version detection | Run exact v1.47 in VM; verify it displays candidate release and exact EXE asset | Frozen v1.47 source excerpt accepts mocked candidate manifest in test_legacy_update.py; actual binary not run |
| Download/install/restart | Exercise old running EXE replacement, candidate bootloader/elevation, protected-directory new helper and readiness, portable manual alternative | Verified downloader/installer fixtures; real migration not run |
| Failure/rollback | Interrupt download, wrong checksum, locked image/marker/backup, failed/early-exit new image, crash before/after readiness, recover and retry |85 updater/installer fixture tests; real frozen lifecycle not run |

The old client's `/releases/latest` cannot see an unpublished draft. Before publication, any test manifest/HTTPS proxy must be confined to the authorized VM and marked simulated-network evidence. Do not change public latest solely to make a test pass. The actual published-endpoint migration remains a final post-publication acceptance check; compare it separately with the pre-publication VM execution proof. Legacy source comparison is compatible with1.49.0, but the old binary's bootloader/relaunch behavior is not established by that comparison.

After these checks and exact-commit green CI, request final human permission to publish. The workflow prepares a draft only from a40-hex reviewed commit and matchingv1.49.0 tag. Review both draft assets and checksum, then publish only when authorized. Download `https://github.com/falker47/Panacea/releases/latest/download/Panacea.exe` and the separately published checksum, validate the new version/size/PE/digest and repeat ZEROfilez normal PC Programs plus Build/PC Setup/Choose Essentials views. Keep ZEROfilez unchanged if its stable entry remains correct.

No row may become PASS from an intention, mock, source inspection or CI artifact alone when it requires real execution or public distribution.

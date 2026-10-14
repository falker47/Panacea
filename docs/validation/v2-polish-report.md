# Panacea 2.0.0 — final UX and functional polish

This report supplements the [V2 audit](v2-release-report.md). The starting commit
was `2f425f453e10cdd917f4673c36e9c0e059f99ff2`, branch
`feat/panacea-brand-dashboard-20261013`, existing draft
[PR #3](https://github.com/falker47/Panacea/pull/3). Version remains **2.0.0**.
The commit containing this report is the reviewed source revision; the final
commit SHA and exact Windows CI run/artifact are recorded in PR #3 and the local
candidate's `VALIDATION.md`. No merge, tag or release was performed.

## Implemented

- Sidebar version/copyright share one bottom-anchored row. Brand text forms a
  compact block beside the original chalice; grid/pack layout handles resizing.
- Only the Dashboard Windows Update, Temporary files and Restore point icons
  grew, from 22 to 40 logical pixels. Their text now wraps to available width.
  Metric icons and sidebar icons retain their dimensions.
- Cleanup's Analyze button is centered against the complete temporary-file
  card, including its result and reasons action, with balanced vertical margins.

### Definitive temporary-file UX

**Analyze** is optional. It never deletes, does not ask for deletion consent and
does not grant later consent. It reports candidate count, approximate recoverable
file bytes, skipped entries and errors, with **No files deleted** in every result,
including failure. Starting analysis from Dashboard opens Cleanup's working view.

**Clean now** is available without analysis. Each click requires explicit
confirmation of permanent deletion. The existing guarded traversal discovers,
validates and deletes in one pass; no mandatory pre-scan was introduced. A previous
analysis is informational only: files are rechecked and totals may differ.
Completed, partial, failed and interrupted results use actual backend counts.
An unexpected exception preserves only progress from the current pass and replaces
old diagnostics, rather than presenting prior analysis as current cleanup evidence.

The native handle/path/object checks, hardlink and reparse refusals remain intact.
Missing approved Temp roots are normal no-op locations; a file disappearing during
enumeration is recorded. Callbacks that fail are diagnosed without losing deletion
counts or stopping protection checks. Manual cleanup remains separate from
Resurrection and its verified-restore-point prerequisite.

Skipped causes come from native Win32 codes or explicit guard refusals. Sharing
violations, access denial, disappeared objects, unapproved roots, identity failures,
hardlinks and reparse points are distinguished only when proven. Other causes
remain unclassified/explicitly recorded. **View reasons** is read-only and keeps
all original records, independently of the bounded 500-line live console. Tests
exercise retention of 1,100 records. Counts refer to diagnosed entries, which may
include directories, rather than guessed counts of inaccessible descendants.

“Recoverable” and “freed” totals are logical file sizes returned by the backend:
candidate file bytes versus successfully deleted file bytes. They are not a
measurement of the volume's allocation/free-space delta.

### Actions and output

Sidebar **Cleanup** navigates; **Analyze** scans; **Clean now** confirms/deletes;
Windows Disk Cleanup **Open utility** only launches Windows and reports that it
opened. External utilities do not claim an observed cleanup completion.

Cleanup details, Optimization output, Command output and Full sequence output
open once at an accepted explicit start. One geometry update reveals the panel
inside the scroll viewport. Streaming remains on the existing worker/dispatcher
path. New messages and completion never reopen a manually closed panel. A new
accepted operation may reopen it; rejected concurrent attempts do not. Navigation
retains output and open/closed state. Restore point and Battery report also route
their results/failures to Tools output. No external PowerShell console was added.

## Verification

- Live baseline: **443 tests passed**. Final suite: **501 passed**, including all
  original coverage and 58 new cases. No tests disabled; old UI wording and mock
  keyword signatures were updated to the legitimate new behavior.
- Targeted tests cover direct one-pass deletion, read-only analysis, denied consent,
  consent after analysis, changed/locked files, actual skips/errors/partial results,
  unexpected interruption, duplicate starts, output routing and diagnostic history.
- Native tests cover Dashboard/Cleanup at **1366×768 and 1920×1080**, each with CTk
  widget scales **100%, 125%, 150%**; footer/brand/icon geometry, centering, resize,
  Return/Tab/PageUp/Ctrl+1…7, manual output closure, navigation and scrolling.
  At smaller additional resize bounds, Dashboard actions remain reachable by scroll.
- Ruff, source compilation/import, whitespace checks and PyInstaller build pass.
- [42 native source screenshots](screenshots/v2-polish-matrix.json): all seven views
  for the six viewport/scale combinations. Read-only startup queries only.
- [21 labeled inert state captures](screenshots/v2-polish-states/): analysis and
  cleanup completion/partial/failure, output closed/reopened, disk/tools running and
  completed, Resurrection running/completed/partial/failed/cancelled and unknown
  states. These demonstrate UI behavior, not successful host maintenance.
- Screenshot captures report no callback errors. Native Windows DPI remained **96**;
  CTk widget scaling is a simulation, not a Windows DPI setting change.
- [Five packaged smoke launches](v2-polish-packaged-probe.json) all exit 0 and expose
  a native 1020×680 client window. Median mapped-window time: **2.33 s**; this is an
  observation, not a statistically supported performance claim.

Visual inspection found and corrected text clipping beside the enlarged Restore
point icon. A native regression found output below the viewport because scrolling
preceded CTk's scrollregion update; the one-time reveal now waits for geometry.
Independent review found stale reasons after exceptions and missing output routing
for two Tools actions. Both have failing-before/passing-after regressions and were
cleared in the final review.

## Candidate

Local file: `dist/v2.0.0-polish/Panacea.exe`, **24,297,905 bytes**.

SHA-256: `18c0a96857676dac89e818bc945ee533b7c11f9d1120109a7a62c18556ee7d0a`

File/product version: **2.0.0**. Local build: Windows 11, Python 3.14.3,
PyInstaller 6.22.3. [Manifest and runtime/build input digests](v2-polish-candidate-manifest.json).
The prior `dist/v2.0.0` candidate is preserved. Windows CI independently builds with
Python 3.12; its artifact/hash are separate and recorded in PR #3 after the final
commit passes CI. Neither candidate is a published release.

## Explicitly unpassed gates

Real sensitive maintenance/Turbo/Resurrection on a disposable Windows machine;
migration from public v1.47; actual Windows DPI changes; normal elevated UAC startup;
installation interruption and rollback. No sensitive operation ran on the host.
No merge, tag, publication or replacement of the existing private release is
authorized by this evidence. Final release approval follows those remaining gates.

**NEXT_ATOMIC_ACTION:** authorize a disposable Windows environment for the remaining
real maintenance, migration, DPI, UAC and rollback validation.

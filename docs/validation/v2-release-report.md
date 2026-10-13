# Panacea 2.0.0 candidate validation

Date: 2026-10-13. Branch: `feat/panacea-brand-dashboard-20261013`.
Baseline: `24e2adede5e7b47506a33e6f49b459d9d61804bd`.
Existing [draft PR #3](https://github.com/falker47/Panacea/pull/3) targets
`codex/panacea-next-generation` / PR #2. No public release, tag change or merge
is part of this work. The older private 1.49.0 draft is not this candidate.

## Implemented

| Section | Final composition and behavior |
| --- | --- |
| Dashboard | Full-width adaptive cards, compact quick actions, readable hardware information, nullable CPU/RAM/system-volume metrics and verified Windows Update counts. No invented healthy zero readings. |
| Cleanup | Preview card, four compact actions with irreversible-deletion confirmations, expandable output; component-store output stays in Cleanup. Preview and partial/skipped/error results persist across navigation. |
| Disk | Local fixed-volume inventory, actual capacity and availability, keyboard drive selection, disabled unavailable optimization and clear Windows utility launch feedback. |
| Tools | Compact repair/network rows, restore point and battery report, expandable command output; bounded streams, Unicode decoding, repaired/restart-required results and saved-report opener errors. |
| Apps | Separate installed/startup destinations and classic Programs; reports only that Windows opened, and replaces previous success when opening fails. |
| Turbo | Observed settings, unknown/disabled states, exact saved originals and explicit partial-profile restoration; delayed queries cannot overwrite a newer mutation. The visual control describes a preference, not proven immediate animation changes. |
| Resurrection | Ten visible phase states, actual attempted/completed progress, mandatory verified restore-point checkpoint, persistent outcome across navigation, cancellation between commands, and no subsequent step after unverified command completion. |

Original gold chalice and midnight-blue/gold palette retained. Eleven authentic
Lucide SVGs are pinned to revision `dab294f313897bacaa968b725b3259fa37c17bd1`,
rendered with an already-installed Sharp/librsvg development tool, and bundled
locally. ISC and inherited Feather MIT notices are retained. Resurrection uses
the original proprietary chalice. No runtime dependency was added. See
[asset provenance and contact sheet](v2-icons.md).

The complete [UI action inventory](v2-ui-audit.md) maps handlers, arguments,
feedback, privileges, concurrency and unverified real effects. Detailed audits:
[maintenance](v2-maintenance-audit.md), [monitoring](v2-monitor-audit.md),
[Turbo/updater](v2-state-update-audit.md),
[independent maintenance review](v2-maintenance-review.md), and
[independent state/update review and capability discovery](v2-independent-review.md).

Unverified command completion persists through reopening using protected,
immutable records and Microsoft's documented successful-boot counter. Ordinary
startup does not create a marker. Unknown, corrupt or unreadable records fail
closed. A strictly newer verified counter permits maintenance again; counter
rollback/wrap does not. Saving runs on the worker before GUI result delivery.
If storage denies every write before any artifact can be created, persistence
across reopening cannot be guaranteed: the current session stays blocked and
the save error remains visible. Invalid/unknown records can require explicit
recovery; restarting is not claimed to repair malformed storage.

Closing during owned maintenance requests sequence cancellation and waits for
the current command to finish instead of abandoning it. A timeout bounds the
direct process and pipe wait; it does not kill arbitrary Windows descendants.
External Windows utilities are launch-only and remain managed by Windows.

## Verified locally

- Baseline exact-source suite: **246 passed**. Final integrated suite:
  **442 passed in 35.39 s**, no skipped tests. Native NTFS and process fixtures
  ran outside the tool sandbox, confined to `build/tests-v2-release-final`.
- Ruff, Python compilation, import/version checks and whitespace checks pass.
  Tests were not disabled or weakened. Failed regressions and sandbox-denied
  intermediate attempts are recorded in the scoped audits.
- Independent maintenance review resolved MR-1 through MR-5: inherited-pipe
  deadlines, CHKDSK exit 1, invalid stdin, reopening after unknown completion
  and unsuitable wall-clock boot identity. Final UI guard review: **46 passed**,
  six native GUI tests intentionally left to the integrated run.
- A separate full UI/monitor/startup/metadata review found no important finding
  in its reviewed snapshot; its 182-test scope excluded six native GUI tests.
  The subsequent deferred-close and persistent-guard changes have their own
  regressions and independent review.
- Six native isolated GUI tests cover seven-section construction, focus,
  Ctrl+1…7, Tab/Enter, drive arrows, Space on inert Turbo controls, scrolling,
  resizing and compact layouts. No maintenance backend is called by those tests.
- [42 final section screenshots](screenshots/v2-final-matrix.json): seven views
  at 1366×768 and 1920×1080, each at CTk 100/125/150%. These are actual Windows
  application captures; widget scaling is simulated. Native window DPI is 96
  throughout; Windows display scaling was never changed. Zero recorded Tk or
  dispatcher callback errors. Baseline views are in `screenshots/v2-before`.
- [13 native fixture-state captures](v2-ui-states.md) cover loading, success,
  partial, error, unavailable, unknown and cancellation. Synthetic results are
  visibly labelled. Their earlier source hashes are retained; later lifecycle
  changes are covered by the final tests, not retroactively attributed to these
  screenshots. The CTk shape-font fallback warning is disclosed in that report.
- Computer Use window discovery succeeded, but state capture timed out waiting
  for app approval. No injected desktop input was performed through that tool;
  keyboard evidence comes from the isolated native Tk regression tests.

The local Windows EXE is **2.0.0**, **24,291,538 bytes**, with SHA-256
`03878f2d1ceb841f3dfe36298e548b348d908fd733c3f80b837a1656d8908e9e`.
All five safe packaged launches mapped a 1020×680 native window and exited 0;
median mapped-window time was 4.049 seconds including one-file extraction.
[Candidate manifest](v2-candidate-manifest.json) binds runtime/build inputs to
the exact binary; [performance report](v2-performance.md) contains comparable
source measurements and their limits. The expanded-details mouse-wheel
regression also passed independently after the 442-test full run.
The PR check page is authoritative for the final commit's
Windows CI; local evidence alone does not establish a green remote run.

## Blocked release gates

1. An explicitly authorized disposable Windows environment for actual cleanup,
   locked-file/browser-profile cases, Recycle Bin, restore points, drive
   optimization, SFC/DISM, network reset, Turbo exact restoration, interruption,
   reboot and unknown-completion recovery. No host maintenance was performed.
2. Real Windows 100/125/150% DPI and representative Windows 10/11 behavior.
   CTk simulation and fixture success do not satisfy this gate.
3. Prior-release elevated packaged migration in a protected install directory:
   ACLs, running-image locks, helper/new-image launch, readiness, interruption,
   failed replacement, rollback, pending recovery and different privilege
   contexts. PE-shaped fixture files were not real executable updates.
4. Final human approval of merge and stable publication after the above gates.
   Review unsigned-binary distribution/provenance; SHA-256 is integrity, not
   Authenticode identity. Revalidate final published assets and download flows.

Read-only capability discovery found Windows 11 Home with no usable authorized
Sandbox/VM. No hypervisor, guest, feature or host setting was installed/changed.
ZEROfilez already uses `/releases/latest/download/Panacea.exe`; deployed source
and the current endpoint were verified without changing the catalog. It still
serves public v1.47, not this candidate.

**NEXT_ATOMIC_ACTION:** designate and explicitly authorize a disposable Windows
guest for the listed sensitive tests. Provisioning, if needed, must specify the
hypervisor/image/license and any permitted host feature changes or restart.

**IMPLEMENTED:** V2 candidate. **VERIFIED:** automated, native isolated and
read-only checks described above. **BLOCKED:** real-system gates and release
approval. **PUBLISHED:** no.

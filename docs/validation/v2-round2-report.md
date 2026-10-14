# Panacea 2.0.0 — final visual polish, Round 2

**PASS for this visual-polish scope.** Baseline:
`4f58bae05f6e19c24da6a0405b4f1e07074f1fa5`, branch
`feat/panacea-brand-dashboard-20261013`, existing draft
[PR #3](https://github.com/falker47/Panacea/pull/3).
The source revision is the commit containing this report. Its exact SHA and final
Windows CI run/artifact are recorded in PR #3 and the local candidate's
`VALIDATION.md`. Version remains **2.0.0**.

## Changes

- Dashboard Windows/system information, Windows Update, Temporary files and
  Restore point use shorter label boxes and balanced outer padding. Titles and
  secondary text form tighter groups; adaptive wrapping remains enabled.
- Main sections gain six logical pixels of space from the sidebar. The update
  strip and bottom operation status follow the same inset.
- Resurrection opens with a short prerequisite line and a prominent status,
  progress bar and Start sequence area. Status has its own full-width row, so
  long running/completion text cannot collide with Start or Cancel.
- The ten numbered phases form a compact two-column grid. A small visible warning
  preserves permanent deletion of browser caches, temporary files and all Recycle
  Bin items; restore points cannot recover deleted files; network reset may
  disconnect or require restart; save work; cancellation stops between commands.
  The verified restore-point prerequisite and full confirmation are unchanged.
- Sidebar footer is one bottom-anchored row: **© 2026 falker47** on the left,
  **v2.0.0** on the right. The credit link, palette, original chalice and icons remain.

Changes are confined to UI composition/copy. Operation handlers, worker/dispatcher
paths, confirmations, cleanup semantics, native guards and all backend modules are
unchanged. The [functional polish report](v2-polish-report.md) remains applicable.

## Verification

- Baseline: **501 passed**. Final complete suite: **501 passed**.
  Existing six native geometry cases were extended; no test was disabled.
- Dashboard/Cleanup/Resurrection geometry, footer baseline and left/right/bottom
  insets, title/detail glyph gaps, all ten readable phases, Start/status/progress,
  full output panel, resize/scroll and keyboard/output lifecycle checks pass.
- Targeted checks: six viewport cases plus all-section visibility, keyboard
  navigation and output persistence. The full suite reran them after final edits.
- Ruff, compilation, import/version, whitespace and PyInstaller build pass.
- [42 native source screenshots](screenshots/v2-round2-matrix.json): seven sections
  at **1366×768 and 1920×1080**, each at CTk **100%, 125%, 150%**. Dashboard,
  Resurrection and footer were visually reviewed in all six combinations.
- [Five labeled Resurrection fixtures](screenshots/v2-round2-states/manifest.json):
  running, completed, partial, failed and cancelled, with integrated output open.
  These are inert backend fixtures, not evidence of real maintenance.
- Captures report **zero callback errors**. Actual Windows DPI stayed **96**;
  CTk widget scaling was simulated without changing Windows display settings.
  Some 1920×1080 captures include a small external Brave overlay at the extreme
  bottom-right, over empty space/scrollbar end; it is not part of Panacea.
- [Five packaged smoke launches](v2-round2-packaged-probe.json): all exit **0**,
  native **1020×680** windows. Median mapped-window time **2.01 s** is an observation,
  not a claimed performance improvement. No UAC or sensitive operation was run.

Visual inspection exposed a lower edge of the Resurrection output panel outside
the scroll viewport at 1366×768/150%. Reduced progress/grid spacing fixes it; the
native geometry matrix now checks the entire panel against the actual canvas.
Independent source and visual review found no remaining blocker.

The first Windows CI run exposed a test measurement error: constructing a new
`tkinter.font.Font` from CTk's pixel-sized descriptor could round it to a different
point size. A local isolated reproduction at Tk text resolution 1.5 measured
**48 px** for the actual rendered text and **58 px** for the copied font, falsely
reporting clipping. The previous geometry test failed under that same setup; the
corrected test passed by querying the original font descriptor directly. Bounds
and tolerances were not relaxed. This matches the class of issue documented in
[CPython #143990](https://github.com/python/cpython/issues/143990). The complete
suite was rerun; runtime sources, screenshots and the local EXE remain unchanged.

## Candidate

Local candidate: `dist/v2.0.0-round2/Panacea.exe`, **24,298,564 bytes**.

SHA-256: `3088e81faea0253f0b775ed562229a9ee7eefd09c2d6b0b450c3f2864ad9efe6`

File/product version **2.0.0**, Python **3.14.3**, PyInstaller **6.22.3**.
[Manifest, runtime/build digests and smoke results](v2-round2-candidate-manifest.json).
Previous local candidates are preserved. CI independently builds with Python 3.12;
its artifact/checksum are separately recorded in PR #3 on the final commit.

## Remaining gates

Real sensitive maintenance, migration from v1.47, actual Windows DPI changes, UAC
and interruption/rollback remain **unpassed**. No sensitive maintenance ran on the
host. No merge, tag, release publication or private-release replacement occurred.

**NEXT_ATOMIC_ACTION:** test manuale finale di Mauri sulla nuova build.

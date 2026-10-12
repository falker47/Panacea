# Persistent work ledger

## Current checkpoint

- UI, command/cleanup/Turbo/restore safety, verified updater and draft release pipeline implemented for 1.49.0 on codex/panacea-next-generation.
- Independent review found five defects; all corrected. Extended native attribute-mask testing found a further cleanup/Turbo path-binding defect; immutable opened-object validation and retained relative-create handles corrected it. A fresh case-sensitivity hypothesis was investigated and its native prerequisite rejected (145); see final-security.md.
- Final integrated suite: 221 passed, zero skipped/failed, including published v1.47 source comparison/detection against a mocked candidate manifest; actual old EXE migration remains unrun. Ruff and compile/import checks passed. An earlier transient Tk read failure remains documented, not hidden.
- Final isolated PyInstaller 6.22.3 package: 24,204,263 bytes, SHA-256 aab331fe38ecf186f5cb1d7f095871d49c4ae4dedfc4b7ffdac79f0d67397484; PE/version1.49.0 and real safe smoke exit0. Unsigned.
- Forty-two final screenshots at two physical sizes and three CTk scales captured and visually reviewed; actual OS DPI changes remain untested.
- Five final source timings and intermediate per-process idle samples recorded in performance-report.md; preserved before evidence excludes UAC/extraction.
- Next: coherent commit/push/draft PR, exact-commit Windows CI, concrete Windows VM verification request. Stable publication, actual prior-version migration and new latest-download/ZEROfilez acceptance remain pending.

## Earlier chronological checkpoint (superseded)

- Mission read in full; active goal follows the mission rather than the completed file-reading subgoal.
- Baseline branch: d605d5c8f135b49ca20c75b85845bf216b648ef0; working branch codex/panacea-next-generation.
- Ruling: retain CustomTkinter and use incremental native changes — no measured reason to migrate — cost if wrong: later framework rework.
- Ruling: candidate 1.49.0 rather than 2.0.0 — preserves existing product and legacy tag comparison — cost if wrong: version renumbering before publication.
- Ruling: three parallel domains own disjoint files; controller integrates startup/release/evidence — minimizes conflicts and allows safety tests to remain isolated — cost if wrong: interface integration rework.
- Ruling: release workflow creates a draft only; stable publication remains a concrete final human gate — real prior-release update/VM verification is not available yet — cost if wrong: manual publication step remains.
- Task 1: baseline compile/import, live CI/release/catalog source and seven screenshots verified; five real hardware and five source startup samples recorded. Packaged cold/warm startup and true OS DPI changes not yet measured.
- Task 5 in progress: eight startup/package tests observed RED then GREEN; main removed forced splash, source/frozen UAC quoting fixed, safe smoke and update dispatch added; spec/version/checksum/build/release workflow prepared.
- Tasks 2–4: independent implementation agents running; individual reports are safety-report.md, updater-report.md, ui-report.md when ready. No agent is authorized to run maintenance on the host.
- Pending: integrated suite, visual correction, before/after timing, local EXE, independent review/security workflow, coherent commit/PR/candidate CI, VM migration and publication approval.

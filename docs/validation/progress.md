# Persistent work ledger

## Current checkpoint

- UI, command/cleanup/Turbo/restore safety, verified updater and draft release pipeline implemented for 1.49.0 on codex/panacea-next-generation.
- Independent review found five defects; all corrected. Extended native attribute-mask testing found a further cleanup/Turbo path-binding defect; immutable opened-object validation and retained relative-create handles corrected it. A fresh case-sensitivity hypothesis was investigated and its native prerequisite rejected (145); see final-security.md.
- Final integrated suite: 231 passed, no skips/failures, including v1.47 source detection with mocked manifest and native monitor process/pipe cleanup; actual old EXE migration remains unrun. Ruff and compile/import checks passed. The earlier transient Tk failure remains documented.
- Final isolated PyInstaller 6.22.3 package: 24,206,497 bytes, SHA-256 6b40342a235824b4f368a4c2c8d131fa53c16385209b0317e82021c5228776d3; PE/version1.49.0 and five real safe smokes exit0. Unsigned.
- Forty-two final screenshots at two physical sizes and three CTk scales captured and visually reviewed; actual OS DPI changes remain untested.
- Fresh post-shutdown-correction source timings: median ready 0.894s / first metrics 0.699s; five packaged mapped-window samples median 1.852s. Earlier cohorts/idle data remain retained.
- PR2 is open/draft, b7e8efb and cac08c8 pushed. CI cac08c8 passed; its orphan log motivated the final monitor correction. Next: final commit/CI. An expressly authorized disposable VM was requested; none supplied yet. Publication, real old-version migration and new latest/ZEROfilez acceptance remain pending.

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

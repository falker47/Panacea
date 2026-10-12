# Panacea Next Generation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for integration and superpowers:dispatching-parallel-agents for the three independent implementation domains; no overlapping file ownership. Use TDD for risky behavior and one independent final code review.

**Goal:** Deliver a safer, responsive Windows maintenance app and verifiable 1.49.0 release candidate.

**Architecture:** Retain CustomTkinter; isolate update, safety and worker orchestration in modules. UI consumes those modules and communicates with workers through a main-thread queue.

**Tech Stack:** Python 3.10+, CustomTkinter, Pillow, packaging, PyInstaller, pytest, GitHub Actions Windows.

**Spec:** docs/superpowers/specs/2026-10-12-panacea-next-generation-design.md

## Global Constraints

- Candidate version: 1.49.0; authoritative version.py; exact asset Panacea.exe and checksum Panacea.exe.sha256.
- No destructive tests or host power/service/registry changes; fixtures and mocks only.
- Keep CustomTkinter and all seven existing sections.
- Stable publication requires CI, real Windows and updater verification, security gate, and final approval.
- ZEROfilez existing latest URL stays unchanged if correct.

## Review Focus

- Windows reparse-point races: cleanup must fail closed and never delete outside approved roots.
- Unicode/spaced executable paths and locks: failed updates leave a working old executable.
- Process launch succeeds then crashes: retain backup until a readiness acknowledgment.
- Late worker callbacks and rapid repeated clicks: no Tk calls off-thread, no conflicting maintenance jobs.
- Existing custom power/service states: restoring Turbo must preserve the exact original values.

## Task 1: Baseline and evidence (controller)

Files: docs/validation/*; scripts/gui_probe.py; scripts/benchmark.py.

- [ ] Verify live main, releases, PRs, CI, Trello and ZEROfilez. Record capability bootstrap.
- [ ] Run baseline compile/import and measure five cold metadata/dashboard samples and five source startup samples. Record raw timings, memory/CPU where available and method.
- [ ] Launch non-elevated source GUI without modifying system settings; capture real baseline windows through Windows Computer Use, retain screenshot files for handoff.

## Task 2: Safe maintenance domain (agent)

Own only modules/cleanup.py, commands.py, disk.py, performance.py, restore.py, optional modules/operations.py and tests/test_cleanup.py, test_commands.py, test_performance.py, test_restore.py, test_operations.py.

Interfaces: preserve existing CleanupManager tuple returns and progress_callback. Add preview_temp_files()->(count,bytes), last_result with skipped/errors. Preserve command methods; run_command_stream returns bool. Disk optimizer returns bool, validates drive letter. Performance setters return (bool,message), getters return actual bool/None; add original-state persistence and exact restoration to existing setters. Restore create returns (bool,message), no implicit enable. Optional sequence utility reports step results for UI integration.

- [ ] Write failing tests for unsafe TEMP roots, symlinks/junctions, outside sentinels, locked files, preview, counts and injected commands/drive letters.
- [ ] Run tests RED, implement protected cleanup and allowlisted subprocess arguments; rerun GREEN.
- [ ] Write failing tests for unknown restore sequence, unchanged sequence, custom power plan restoration and originally stopped services; implement verified restore and persisted Turbo snapshots; run GREEN.
- [ ] Test command/step failure and cancellation semantics using mocks; document actual tests in docs/validation/safety-report.md. Do not commit while agents run concurrently.

## Task 3: Verified updater domain (agent)

Own only modules/updater.py, optional modules/update_install.py, tests/test_updater.py and tests/test_update_install.py. No UI/main/spec/workflow edits.

Produce UpdateClient(repo,current_version), check()->Release|None (explicit exceptions), download(release, directory, progress=None)->Path, Release.version/release_url/exe_url/size/sha256_url. Expose robust is_newer(remote,local). Produce install_verified(staged,target,expected_sha256,launch)-> result with backup/rollback; establish readiness acknowledgment helper if needed. Coordinate exact APIs with UI agent directly and controller.

- [ ] Write failing version, manifest, missing/duplicate checksum, foreign URL and exact-asset tests; implement and run GREEN.
- [ ] Fake HTTP responses for interrupted/wrong-size/checksum-mismatch/download cancellation; assert no unverified executable returned and no leftover partial file; implement and run GREEN.
- [ ] Test lock/permission failures, replacement and launch failure rollback, backup retention and readiness acknowledgment using fixtures. Implement minimally without arbitrary shell helpers. Report limitations honestly in docs/validation/updater-report.md.

## Task 4: Desktop presentation and worker domain (agent)

Own only panacea_ui.py, modules/ui_dispatch.py, modules/system_monitor.py and tests/test_ui_dispatch.py, tests/test_system_monitor.py, tests/test_ui_controller.py. No main/version/updater/safety/workflow edits.

Consume Task 2 existing signatures and Task 3 APIs. Coordinate updater interface with its agent. Main-thread callback queue, bounded logs, operation guard and shutdown. Redesign existing screens with shared subdued palette, active navigation and readable compact layout. Separate fast dashboard sample from slow hardware metadata, monotonic cache, unsigned battery bytes and 64-bit uptime. Manual updater check, notes/defer/retry and verified download. Replace unsafe old update/swap logic. Safe confirmations, exact Turbo state refresh and Resurrection per-step results/critical failure stop/cancel summary.

- [ ] Write failing worker shutdown/duplicate/dispatch tests and monitor timing/API tests; implement and run GREEN.
- [ ] Apply UI layout and typography changes, focus bindings, resize charts and useful dashboard shortcuts.
- [ ] Integrate new updater and maintenance APIs. Confirm all callbacks avoid off-thread Tk, terminal status persists, buttons reset on exceptions and critical failures are reflected.
- [ ] Run compile/import and controller tests; report in docs/validation/ui-report.md. Do not launch desktop GUIs or run host modifications; controller owns screenshot verification. Do not commit while agents run concurrently.

## Task 5: Startup, packaging and release (controller)

Own main.py, version.py, Panacea.spec, .github/workflows/*, scripts release/build/benchmark/gui_probe, requirements files and README/release documentation.

- [ ] Write failing version/package/CLI safety tests where behavior merits them.
- [ ] Remove artificial splash delay, fix resource path and UAC quoting/frozen invocation; add safe smoke/readiness modes as updater requires.
- [ ] Add deterministic Windows build, PE version metadata, checksum, dynamic version/tag validation; tests/compile/import/EXE smoke in CI.
- [ ] Prepare draft release workflow and release notes with stable publication approval gate. Build locally, verify PE and checksum, launch safe EXE.
- [ ] Capture main screens after, inspect and correct layout; run requested dimensions/scales and performance before/after. Record unavailable evidence as NOT RUN.

## Task 6: Review, CI and distribution gates (controller + independent reviewer)

- [ ] Run complete tests, static checks, compile/import and real EXE safe smoke. Review safety and whole diff independently, fix important findings with regression tests.
- [ ] Commit on work branch, push once coherent, create draft PR, attach it and wait for candidate CI result.
- [ ] Prepare self-contained CHATGPT_CODEX_HANDOFF_V1 with actual evidence and pending gates.
- [ ] Request final stable publication approval only when all preceding release gates pass. Until then RESULT=PARTIAL or RELEASE_PENDING. Do not mark mission complete.

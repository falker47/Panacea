# Panacea Next Generation design

The binding mission is the user-supplied goal-objective.md dated 12 October 2026. The user authorizes autonomous, reversible technical decisions and requests implementation, not an audit alone. Stable publication requires final human approval. Candidate version: 1.49.0, preserving the legacy v1.47 update discovery contract and exact Panacea.exe asset name.

## Approach

Retain Python and CustomTkinter. A framework migration increases packaging and regression risk without evidence that Tk is the limiting factor. Separate risky filesystem/update/command orchestration from presentation. Reuse existing icons. Preserve Dashboard, Cleanup, Disk, Tools, Apps, Turbo and Resurrection.

Three alternative paths were considered: cosmetic changes alone would leave elevated-system risks unresolved; framework replacement would consume effort without measured justification; incremental native improvements provide testable safety and meaningful UX changes. The third is selected under the mission's autonomy authorization.

## Safety and operational contracts

Cleanup operates only on validated user/system temporary directories and explicit browser cache roots; reject broad roots and reparse points, never traverse junctions/symlinks, count actual deletions and expose preview/skips. Tests operate on temporary fixtures only. Commands accept known maintenance commands and explicit arguments, never arbitrary shell fragments. Drive input must be a single drive letter. Restore creation is successful only if a new sequence number is verified; unknown/unqueryable state is failure. Enabling System Restore requires explicit user action.

Turbo saves original power scheme, service running state and visual setting before mutation, preserves it across restarts, and restores it instead of applying defaults. Unknown state must not be shown as disabled. Master changes and individual changes are serialized. No system modifications occur on startup or in GUI verification.

Resurrection confirms the irreversible cache/recycle deletion and network reset, verifies restore point first, records every completed step's result, halts before destructive steps when the safety prerequisite fails, distinguishes failed/partial/cancelled/completed, and cancels only between commands. Progress advances when a step finishes.

## Updater

GitHub Releases remains authoritative. packaging.version handles legacy and semver tags; stable checks reject draft, prerelease and downgrade. The manifest selects exactly Panacea.exe and Panacea.exe.sha256, validates repository-owned HTTPS asset/release URLs, size and checksum format. Downloads use exclusive temporary files, bounded reads and progress, verify advertised size, SHA-256 and PE header, and never execute unverified data.

Installation preserves a backup, handles lock/permission failure without closing the old app, verifies the staged bytes again, checks launch errors, and rolls back on failed launch. Keep backup until the new app acknowledges readiness; do not indiscriminately remove old/updater files at startup. Prefer a small self-update mode in the existing signed/unsigned application over generated shell helpers. Do not claim Authenticode signing without a certificate.

The UI checks in a worker at startup, offers a manual check with offline/rate-limit feedback, release notes, defer, retry and manual download. Source execution opens the verified release page rather than swapping python.exe. Expose downloading/verifying/installing/restarting status. Real prior-release migration remains a required release gate.

## UI and lifecycle

Use Segoe UI, restrained dark surfaces, one blue accent, accessible text contrast and a clearly highlighted active sidebar item. Compact headings/cards, readable logs, useful dashboard actions and independent fast metric loading versus slow hardware metadata. No decorative hero, claims of guaranteed speed, or weekly-restart advice without evidence.

Workers post messages into a queue drained by Tk's main thread. Never invoke Tk methods from workers. Bound pending callbacks and log history, prevent duplicate operations, ignore late callbacks after shutdown, and prevent shutdown while an update replacement is underway. Keep charts responsive on resize. Windows screenshots before/after and layout at 1366x768 and 1920x1080 with 100/125/150% scaling are evidence requirements, not assumptions.

## Performance and release

Collect at least five equivalent samples for a significant hotspot, startup readiness and refresh; record environment and raw results. Split fast metrics from slow metadata to remove the initial hardware-query delay; static metadata uses monotonic TTL cache. Do not run cleanup or repairs as benchmarks.

CI runs tests, compile/import checks, Windows packaging, version/tag checks and a packaged safe smoke. Release workflow produces exact Panacea.exe, PE metadata and separate SHA-256, creates a draft release by default, and uses a protected publication environment for stable release approval. A CI artifact alone is not release completion.

ZEROfilez must retain Essentials, icon, name and its existing latest/download/Panacea.exe URL. Read and verify its live catalog; change nothing if already correct. After authorized publication independently download latest and compare checksum. Preserve an explicit pending-gate handoff until all mission gates pass.

# Verified updater implementation report

Date: 2026-10-12. Branch: `codex/panacea-next-generation`.

Implemented only `modules/updater.py`, `modules/update_install.py`, `tests/test_updater.py`, `tests/test_update_install.py`, and this report. Main/UI integration was coordinated with their owners; no GUI was launched, no application executable was replaced or executed, and no release was downloaded during these tests.

## APIs and integration

`UpdateClient(repo, current_version, *, opener=None, timeout=20)` exposes:

- `check() -> Release | None`: `None` means an equal/older or unstable release, not an offline check. Failures raise explicit exceptions.
- `download(release, directory, progress=None) -> Path`: callback receives `(received_bytes, advertised_bytes)`; returning `False` cancels. Only a verified executable is returned.
- `fetch_checksum(release) -> str`: validates the checksum asset and returns a lowercase 64-character SHA-256.
- `is_newer(remote, local) -> bool`: `packaging.version` handles legacy `v1.47`, normalized versions and semantic versions; prerelease/development versions are excluded.

Frozen `Release` fields are `version`, `release_url`, `exe_url`, `size`, `sha256_url`, and optional `notes`. Errors are `UpdateError`, `UpdateNetworkError`, `UpdateRateLimitError`, `UpdateManifestError`, `UpdateVerificationError`, and `UpdateCancelled`.

`install_verified(staged, target, expected_sha256, launch, *, protected=False) -> InstallResult` is a filesystem primitive. Its caller supplies an authoritative digest; this primitive alone does not authenticate a CLI-provided digest. `launch(path, token)` returns a process with `poll()` or `None` for an injected launcher. `InstallResult` contains `success`, `backup`, `error`, `rolled_back`, `readiness_token`, and `process`. Success means launch was accepted; it does not mean startup readiness.

Frozen UI integration uses `start_self_update(staged, target, release, client) -> SelfUpdateJob`. `job.poll()` returns a `status` and `message`; statuses are `preparing`, `installing`, `waiting_ready`, `ready`, and `failed`. Keep the old GUI open until `ready`. Installation/permission failures leave it open. Source execution must open `Release.release_url` for manual installation.

Main dispatches `--panacea-update-helper WORKSPACE` to `run_update_helper(workspace) -> int` before Tk/UAC startup. The helper is a copy of the current installed image, not the newly downloaded executable. It launches the installed verified image with `--panacea-update-ready TOKEN`. After the new GUI initializes, main calls `acknowledge_ready(sys.executable, token) -> bool`. The token is 64 random hexadecimal characters. `readiness_path(target)` identifies the pending marker.

## Verification and trust boundaries

Release discovery selects exactly one `Panacea.exe` and one `Panacea.exe.sha256`. Drafts, prereleases, downgrades, malformed manifests, missing/duplicate assets, foreign repositories, non-HTTPS URLs, credentials, raw control characters, and mismatched release tags fail closed. GitHub repository URLs are required initially; HTTPS redirects may reach GitHub's release-assets CDN. Metadata cannot originate from that CDN.

Manifest reads are limited to 1 MiB, checksum reads to 4096 bytes, and executable reads to the advertised size with a 512 MiB ceiling. Downloads use exclusive files, delete owned partial files on failure/cancellation, preserve preexisting collision files, and verify the copied result again. Verification includes exact advertised executable size, SHA-256, DOS/PE signatures, supported COFF machine, executable/non-DLL characteristics, optional-header magic and bounds, and section-header bounds.

The helper re-fetches `version.GITHUB_REPO`/`VERSION` from its own trusted code and obtains the authoritative manifest/checksum itself. A supplied CLI digest is never an elevated trust authority. The release version must still match the prepared version. Staging is copied into a protected workspace and verified again immediately before installation.

Elevated automatic updates require an administrator-owned/protected installation tree and current executable. Win32 owner/DACL inspection rejects lower-privilege write/control access and unsafe ancestor ownership/delete-child control. Directories and executable/state files are created with explicit Administrators ownership and a SYSTEM/Administrators DACL at creation. Reparse points/symlinks are rejected. This deliberately refuses automatic replacement from user-writable Desktop/Downloads installations; those installations retain manual download.

Installation copies into an exclusive candidate and verifies those exact open-file bytes. Backup names are exclusively reserved; existing candidate/backup collisions are preserved. Rename/permission failures preserve the current executable. Replacement or launch failure rolls back where possible; failed rollback retains the old executable at the reported backup path. A launched process that exits before readiness causes rollback. A readiness timeout terminates the new process before attempting rollback; if it cannot be stopped, the backup is retained.

Backup deletion requires the correct readiness token, matching installed digest, matching backup digest, and the exact generated backup path. Startup acknowledgment is recorded before housekeeping. A locked cleanup file does not invalidate successful startup; its backup/marker remain. No indiscriminate startup cleanup was added. Protected helper workspaces remain for explicit later housekeeping/review.

GitHub/checksum trust is not Authenticode signing. No certificate/signature claim is made.

## Evidence

Tests were written and run RED before the corresponding implementations. Additional RED/GREEN regressions caught malformed PE headers, download filename collision deletion, candidate/backup collision overwrites, and readiness cleanup failure handling.

| Check | Result |
| --- | --- |
| `python -m pytest tests/test_updater.py tests/test_update_install.py -q --basetemp build/tests-updater` | 74 passed, 0 failed |
| `python -m py_compile modules/updater.py modules/update_install.py tests/test_updater.py tests/test_update_install.py` | Passed |
| Fake network: stable/version/asset/url/checksum validation; offline/rate-limit/interrupted/wrong-size/cancelled downloads | Passed; no real HTTP requests |
| Temporary PE fixtures: permission/lock/replacement/launch failure, rollback failure, early process exit, readiness, forged backup path, path collisions | Passed; launch/process and privileged ACL creation boundaries injected |
| Native Win32 owner/DACL read-only probe on this Windows host | `C:\Program Files` and `C:\Windows` accepted; Desktop workspace rejected |
| Latest whole-project snapshot: `python -m pytest -q --basetemp build/tests-updater-full` | 157 passed, 3 failed while UI agent was adding its final changes |

The full-suite snapshot's failures were `tests/test_ui_controller.py::test_centering_preserves_requested_geometry_when_it_fits`, `::test_centering_clamps_large_geometry_to_scaled_work_area`, and `::test_battery_report_uses_system_directory_and_single_output_path`. They were reported to the UI owner/controller; no updater test failed. The controller must run the integrated suite again after all agents finish.

## Remaining release gates

- Real packaged, elevated protected-directory file/directory creation and process launch: **NOT RUN**. Unit tests replace that privileged boundary; the read-only ACL probe does not establish real elevated installation success.
- Actual Windows running-image rename/lock behavior and paths with spaces/Unicode: fixture paths and injected lock failures pass; real running executable migration is **NOT RUN**. If Windows denies rename, automatic installation reports failure without closing the old GUI.
- Real previous-release migration, restart/readiness/crash recovery, and final latest-asset checksum verification: **NOT RUN**; required before stable publication.
- Authenticode certificate/signing: **NOT PROVIDED**.

The updater domain is implemented and fixture-verified. These results do not establish a production migration or stable-release approval.

## Independent review correction: readiness cleanup recovery (I1)

The independent review in `docs/validation/code-review.md` identified a real lifecycle failure: successful readiness could retain a locked backup/marker, while every subsequent install rejected that completed marker even after the lock released. Both backup-unlink and marker-unlink variants were reproduced RED with PE fixtures and injected transient `PermissionError` failures.

The correction adds `finalize_ready(target, *, token=None, protected=False) -> bool`, an idempotent finalizer. Before another install, the existing record must indicate completed readiness and bind the exact target, 64-character operation token, generated backup path, installed SHA-256/PE, and backup SHA-256/PE when that backup still exists. Protected production records must retain their protected flag and trusted owner/DACL. Missing backups are accepted only for acknowledged records, covering backup deletion followed by a locked marker. Pending, malformed, foreign-path or mismatched records retain their marker and backup. A still-locked completed record blocks replacement with retry feedback; releasing that lock permits the next install without a sweep of updater filenames.

Protected install/acknowledgment/finalizer transactions use a per-target global Windows mutex around marker validation, deletion and replacement. This prevents a delayed finalizer from removing a subsequent operation's marker. Abandoned mutex ownership permits acquisition but does not bypass validation of persisted recovery state. In-process fixture transactions use a reentrant lock.

The helper now retries scoped finalization after valid acknowledgment. If an old application's running-image lock still prevents cleanup, its durable completed record remains for the next update. Helper readiness waits are tied to its own backup/token, so a later installation's marker cannot make an older helper wait, remove the newer marker or terminate the ready process. Timeout termination and rollback additionally validate the original pending operation; changed or already-acknowledged state retains its backup instead of overwriting another update.

Fresh verification after this correction supersedes the earlier intermediate full-suite failure snapshot above:

| Check | Result |
| --- | --- |
| `python -m pytest tests/test_updater.py tests/test_update_install.py -q --basetemp build/tests-updater-recovery` | 85 passed, 0 failed |
| `python -m pytest -q --basetemp build/tests-updater-recovery-full` | 188 passed, 0 failed |
| Updater/test `py_compile` and `ruff check` | Passed |

No real executable was launched/replaced and no host maintenance settings changed. Privileged filesystem/launcher boundaries remain injected in helper regressions. Real elevated packaged migration, running-image locks, and cross-process updater-mutex contention/abandonment remain release verification gates; this correction does not claim those gates ran.

## Independent frozen process restart environment

Both process launch boundaries now pass a fresh copy of `os.environ` with `PYINSTALLER_RESET_ENVIRONMENT=1`: launching the copied current-image helper and restarting the installed verified target. The parent environment and private `_PYI_*` variables are preserved. PyInstaller's bootloader performs its own supported environment reset and security validation; updater code does not alter private bootloader state or weaken validation. The public reset variable starts an independent application instance with a fresh onefile extraction, as prescribed by [PyInstaller's public environment variable documentation](https://pyinstaller.org/en/stable/advanced-topics.html#public-environment-variables).

Mock launcher boundary tests first failed RED because both launch sites omitted `env`. After the change they pass GREEN, preserving unrelated sentinel values and inherited private variables, overriding an inherited reset value of `0` only in the copied child environment, and leaving the parent environment unchanged.

Latest scoped verification: 85 updater/installer tests passed with `--basetemp build/tests-updater-pyinstaller`; updater/test `py_compile` and Ruff passed. The simultaneous full-suite snapshot was 202 passed and one failure in `tests/test_cleanup.py::test_alternate_reparse_access_masks_never_escape_live_guard[256]`, the cleanup access-mask correction still owned by the controller/safety agent. No updater test failed. The controller must perform final integrated tests and the clean patched-toolchain build after that correction.

No host process was launched by these environment tests. Actual packaged helper/restart extraction and bootloader validation remain part of the coordinator's clean-build/migration gates.

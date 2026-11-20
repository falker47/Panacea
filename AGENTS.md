# Working on Panacea

Panacea is a Windows maintenance application. The packaged entry point is
`qt_app/main.py` (PySide6 6.10.2, Qt Quick). The legacy Tk entry point is
`main.py`. Use Python 3.12 and the versions pinned in `requirements-dev.txt`.
`scripts/build.py` uses PyInstaller 6.22.3 and `Panacea.spec` to create the
one-file executable. `scripts/build_installer.py` builds the Inno Setup 6
per-machine installer from the verified executable.

## Development checks

Use a project-local virtual environment. On Linux run from the repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q tests -rfE
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s qt_app/tests -p 'test_*.py'
.venv/bin/python -m compileall -q main.py panacea_ui.py version.py modules qt_app scripts
```

On Windows use `.venv\Scripts\python.exe` and set `QT_QPA_PLATFORM=offscreen`
in the test environment. Keep an untouched base checkout. Run the same suites
with the same interpreter and dependencies on the base and candidate. Save
failing pytest node IDs, Qt test names and raw logs. Investigate each new
failure. Linux exercises fixture and source contracts. Windows CI additionally
covers Win32, native packaging, protected directories and Inno Setup.

## Safety

- Keep executable commands in the exact `CommandRunner._COMMANDS` allowlist.
  Use argument vectors. QML and user-entered text must never select arbitrary commands.
- Maintenance mutations require preparation, explicit confirmation, a one-use
  nonce, and a MaintenanceGuard lease and journal. Keep inspections read-only.
- Use fixtures and mocks for local tests. Installation, native replacement,
  rollback, uninstall and system changes belong on disposable GitHub-hosted
  Windows runners. Require an authorized same-repository PR or main, the
  hosted probe opt-in, the runner environment checks and the existing
  `disposable_guard`. Use Actions artifacts for evidence and binaries.

## Compatibility with installed releases

- Preserve `version.GITHUB_REPO = "falker47/Panacea"` and stable `vX.Y.Z`
  releases on `releases/latest`. The portable executable must be the first EXE
  uploaded for the legacy banner. Keep the assets `Panacea.exe`,
  `Panacea.exe.sha256`, `PanaceaSetup.exe`, and `PanaceaSetup.exe.sha256`.
- Ship a one-file `Panacea.exe` to `{autopf}\Panacea`. Preserve Inno AppId
  `{B6C0FB10-27BC-4E6F-9078-40F9E8B49B2D}` and `panacea-language.ini`.
- Preserve helper dispatch with `--panacea-update-helper WORKSPACE`, startup
  acknowledgment with `--panacea-update-ready TOKEN`, and `--smoke-test`.
  `--smoke-backend-imports` belongs to the shipped Qt entry point only.
- The readiness marker is `Panacea.exe.update-ready.json`. The cross-process
  mutex is `Global\PanaceaUpdater.` followed by SHA-256 of the UTF-8 encoded,
  normalized absolute target path. Acknowledge only after QML has loaded and
  the event loop starts. The CI budget is 15 seconds within the shipped
  helpers' 30-second timeout.
- Any change affecting the updater requires an upgrade test from installed
  v2.1.1. Review all three of `modules/updater.py`, `modules/update_install.py`
  and `qt_app/update_flow.py` for changes to the protocol.

## Release and evidence

The general `release.yml` workflow takes a reviewed immutable source SHA and
matching version tag and prepares a draft. Publication is a separate human
decision. Historical version-specific publishing workflows are scoped to their
own releases. Compatibility test stamps are temporary and must never be
tagged, committed or published. For PR evidence, follow `ci.yml`: check out
`github.event.pull_request.head.sha || github.sha`, compare it with `git rev-parse HEAD`,
and record the verified SHA in the job summary. For author and publisher links,
use the master site referenced in `packaging/Panacea.iss`.

See [update compatibility](docs/validation/update-compat.md) for the probe
matrix and report fields and [future update acceptance](docs/validation/future-updates-contract.md)
for the live release checks.

# Prepublication update compatibility

The **Update compatibility** workflow builds the PR head once and exercises
that candidate before a draft or public release exists. Check that each job's
checkout SHA and the `sha` in its JSON correspond to the revision under review.

| Job | Evidence on a passing run |
| --- | --- |
| `linux-contract` | Compares pytest and Qt failure IDs with the untouched base. Exercises the asset, packaging, CLI, mutex and readiness guards with test-local mutations. Records live asset order when the read token is available. |
| `build-candidate` | Builds the real one-file executable, installer and both checksum files using the normal release scripts. `candidate.json` binds the PE version and portable digest to the checkout SHA. |
| `client-acceptance` × five | Extracts version and client code from each pinned original binary under Python 3.12. Runs discovery, checksum and PE validation on the PR asset with an explicit in-memory opener. |
| `client-summary` | Collects all five rows. Missing reports, wrong SHAs or unexpected canonical outcomes fail the gate. The lower-case variant is informational. |
| `transaction` from v2.0.2, v2.1.0 and v2.1.1 | Installs pinned Setup in Program Files and checks the installed EXE pin. Runs the published replacement routine in a frozen test host. Checks the live candidate window title, installed digest, candidate client's second check, sidecar bytes, original AppId, file set and uninstall. |
| `rollback` from v2.1.1 | Tests a purpose-built executable that exits and another that sleeps through the shipped acknowledgment deadline. Requires failed status for the expected reason, exact restored bytes, a working old smoke launch, and a subsequent successful candidate transaction in the same installation. |
| `manual` from v2.1.1 | Runs candidate Setup silently over Italian v2.1.1 using the default directory and persisted language. Checks the candidate bytes, one registration, sidecar and clean uninstall. |

## Test boundary

The helper transaction uses the installed binary's extracted `modules.updater`
and `modules.update_install` after verifying the entire executable against a
published SHA-256 pin. A separate frozen test host calls `run_update_helper`
with its supported `client_factory` argument. Only the exact candidate and,
in the rollback job, the two inert fault images are eligible. Their digests
are embedded in that job's test host. ACL checks, protected copies, job file,
mutex, replacement, restart, acknowledgment and timeout use the published code.
The candidate's actual Qt process must acknowledge startup.

The fixture supplies release metadata, a repository asset URL and a simulated
302 hop to a CDN URL with a query. It logs each request. The operating system's
trust store, proxy configuration and runner traffic need no changes.

**Coverage gap.** The original `Panacea-updater.exe --panacea-update-helper`
process, original GUI's automatic discovery and consent dialog, and real
network/TLS transport of a PR candidate are outside this probe. A passing run
cannot certify those paths. The legacy main.py backend-import smoke flag is a
documented expected failure. The published Qt entry point implements that flag.
Physical UAC prompts, abrupt power loss, third-party endpoint protection and
the public CDN also require separate evidence.

## Running and interpreting the results

Open a same-repository PR, push an authorized change to main, or manually run
**Update compatibility** on main. Fork PRs run the Linux contracts. Windows
probes require the GitHub-hosted disposable runner and explicit opt-in.
For local contract development, run the tests in a fixture-only environment:

```sh
.venv/bin/python -m pytest -q tests/test_update_contract_freeze.py tests/test_update_compat_*.py
```

Download `update-candidate-<sha>` for the candidate and its manifest.
`acceptance-v*` contains the per-version client decision and request log.
A supported canonical client must accept the candidate. v2.0.0 and v2.0.1 must
reject the canonical repository spelling at the release-page check. The table
also shows whether changing only the repository capitalization helped them.

In `native-<tag>-<mode>`, the top-level probe report records PASS or FAIL.
`helper-<case>.json` records status transitions and monotonic timestamps at
the published routine's status writes. Success must advance through
`preparing`, `installing`, `waiting_ready`, `ready`. More than 15 seconds from
`installing` to `ready` fails the job even when the update otherwise succeeds.
Rollback reports include the failure reason and restored EXE hash. A missing
report after a download, installer or build failure leaves that path unverified.
Actions logs identify the failing step. Job artifacts are retained for seven days.

The stamp keeps a source version that is already newer than all fetched
version tags. Otherwise it selects a higher stable patch (2.1.1 becomes
2.1.101 when v2.1.1 is highest). Any generated notes and modified version
exist only in the disposable build checkout. The generic release workflow's
upload arguments are checked locally. The GitHub API's current asset order
is recorded separately because a command's argument order cannot certify
what the service will return.

## Adding the next published version

After 2.2.0 is published, obtain its official portable and Setup assets and
verify their bytes against the published checksum files. Add both reviewed
SHA-256 pins to `scripts/update_compat/published.py`, add the version to the
client and transaction matrices and their workflow tests, and move the
immediately previous stable manual and rollback coverage as appropriate.
Keep the oldest supported installed version. Add the portable digest to the
read-only diagnostic and review the expected legacy rejection rows. If the new
binary embeds a different Python ABI, use a matching interpreter to read
its bytecode. Verify all matrix rows on a new exact-SHA run.

## Read-only update diagnostic

`scripts/Get-PanaceaUpdateDiagnostic.ps1` comes from the updater-recovery
investigation. It hashes the selected Panacea.exe, reads its file version,
matches known published digests and optionally inspects the latest release's
metadata. With `-Offline` it only inspects the local executable. Without an
explicit path it prompts for a file. The JSON on stdout includes the path
with the user profile prefix redacted. Review it before sharing.

```powershell
.\scripts\Get-PanaceaUpdateDiagnostic.ps1 -ExecutablePath "$env:ProgramFiles\Panacea\Panacea.exe" -Offline
```

For the separate live release and postpublication gates, see
[future update acceptance](future-updates-contract.md).

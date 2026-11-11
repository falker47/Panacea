# Future Panacea in-app update acceptance

**Scope:** stability contract for releases **after** v2.1.0. This is a
release checklist, not evidence that an unpublished future binary works.

## Supported user paths

- **Installed v2.1.0+ in protected Program Files:** after startup becomes
  idle, the application checks official GitHub stable releases/latest metadata
  and can offer a newer release. Installation requires user confirmation,
  SHA-256 verification, and the protected helper/readiness/rollback path.
  It is not silent or unattended.
- **Portable copies in Downloads/Desktop:** may discover new releases, but
  the protected updater refuses replacement from user-writable directories.
  Users must replace the EXE manually. Never advertise portable as auto-installable.
- **Installed v2.0.0/v2.0.1 and V1:** require a one-time manual migration using
  the official Setup; new releases cannot patch old executable code remotely.

ZEROfilez permanent releases/latest/download URLs keep its *downloads* current,
not previously installed programs.

## Required gates for each subsequent stable release

1. Preserve repository identity falker47/Panacea and the exact asset names:
   Panacea.exe, Panacea.exe.sha256, PanaceaSetup.exe,
   PanaceaSetup.exe.sha256. Preserve Panacea.exe identity, the installer
   AppId, and the trusted updater helper/readiness contract; explicitly
   review any compatibility-breaking change.
2. On the candidate commit, run the full automated tests including
   tests/test_future_updater_contract.py, native Windows packaging, protected
   install/upgrade, verification failures, and rollback. Verify required
   checks on the exact commit SHA. The synthetic future-version unit test
   only covers version/URL/checksum handling, NOT a real unpublished upgrade.
3. Before declaring the next rollout complete, use a disposable Windows VM
   with the previous official stable installed. Drive a real in-app upgrade
   from its GUI using LIVE public GitHub metadata and the newly published
   assets. Verify consent, exact installed SHA-256, readiness, restart,
   no repeat offer, original AppId, and tested failure/rollback paths.
   Preserve logs and screenshots. The historical v2.0.2 -> v2.1.0 example:
   https://github.com/falker47/Panacea/pull/9
4. Check published releases/latest and both ZEROfilez download links after
   publication, including asset bytes against corresponding checksum files.
   A failed gate is a release incident, not PASS. Do not declare rollout
   complete while a required upgrade check is unverified.
5. Never exercise destructive maintenance or forced rollback on the owner's
   PC. State separate limits for physical UAC, abrupt power loss and hardware.

**Limit:** No finite tests can guarantee all future binaries, network failures,
security software or pre-existing installations. A live future release is
needed for an end-to-end upgrade test. A synthetic fixture cannot prove it.

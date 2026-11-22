# Panacea 2.2.0 release checklist

All boxes start open. Record the reviewed source SHA, workflow links, public
asset digests and VM evidence alongside each result. The release owner decides
when to publish the prerelease and when to promote it to Latest.

## Before publication

- [ ] Review the exact release commit on main. Verify the version and notes
  for 2.2.0 and link its CI, Qt, Windows features and
  [update compatibility](update-compat.md) results. Inspect the five pinned
  client rows and the upgrade and rollback reports. Check the 15-second
  readiness budget. Compatibility builds can use a temporary version stamp;
  identify the final release binaries by their own digests. Verify that the
  release workflow's build job passed the bundle inventory check
  (`scripts/verify_bundle.py`) before signing.
- [ ] Record the repository-capitalization decision. On the T1 candidate,
  installed-client code from v2.0.0 and v2.0.1 rejected canonical URLs and
  accepted the simulated lower-case variant. A repository rename requires a
  separate owner decision and verification of official URLs and old clients.
  With the existing identity, direct these two versions to the official Setup
  for a one-time migration. Recheck the supported canonical rows for v2.0.2,
  v2.1.0 and v2.1.1. [T1 results and decision](https://github.com/falker47/Panacea/pull/18#issuecomment-7038891959)
- [ ] Prepare two disposable Windows installations from the published v2.1.1
  and v2.0.2 installers. Record their installed hashes and snapshots. Confirm
  v2.1.1 is the stable Latest and retain its release link for recovery.
  Verify the [draft workflow](../../.github/workflows/release.yml) used the
  reviewed SHA and that the executable and Setup match their checksum files.

## Prerelease and stable rollout

- [ ] With publication approval, publish the reviewed assets as a prerelease.
  Verify v2.1.1 still resolves through `releases/latest`. Download
  `Panacea.exe` and `PanaceaSetup.exe` from the prerelease and compare each
  with its corresponding published SHA-256 file and the reviewed bytes.
- [ ] With promotion approval, promote those same bytes to stable Latest.
  Verify the public latest endpoint returns `v2.2.0` and lists `Panacea.exe`
  as the first executable. Check both ZEROfilez download paths as described in
  the [stable release gates](future-updates-contract.md).
- [ ] Immediately exercise both installed GUIs against the live endpoint.
  On each, discover the update, confirm installation, and observe the shipped
  helper replace and restart Panacea. Record the version, digest, readiness
  acknowledgment, preserved installer registration and absence of a repeated
  offer. Preserve the VM logs and screenshots. Record failure and rollback
  coverage and any remaining gaps separately. [T1 release evidence](https://github.com/falker47/Panacea/pull/18#issuecomment-7054095001)

If a live gate fails, stop the rollout and restore v2.1.1 as Latest. Verify
the latest endpoint and both download paths again. Record which installations
already upgraded and their recovery outcome. Changing Latest changes what
clients discover. Existing installations require their own recovery.

After a successful rollout, add the reviewed 2.2.0 pins following the
[compatibility matrix instructions](update-compat.md#adding-the-next-published-version).

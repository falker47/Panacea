# Independent V2 state/update review and environment discovery

Date: 2026-10-13. Review baseline: `24e2adede5e7b47506a33e6f49b459d9d61804bd`. Reviewed the working-tree diff in `modules/performance.py`, `modules/updater.py`, `modules/update_install.py`, and their corresponding test files. The reviewer did not author those changes and did not review its own maintenance changes here.

## Findings

**No actionable important correctness regression found in the reviewed diff.** This is a focused independent review, not a claim that all updater/Turbo behavior or the full repository is defect-free.

Inspected:

- Restoring unsaved Turbo keys before attempting live reads; saved-but-unknown keys still fail closed.
- Durable original-state reload and transaction locking behind `get_saved_settings()`; unreadable state remains distinct from an empty record.
- Owned exclusive JSON file cleanup after write/flush failure; preexisting collisions are preserved.
- Rollback success reporting when the original executable has been restored but marker deletion is locked.
- Subsequent cleanup of a rollback marker only after validation of token, target, backup path, protection flag and original digest; pending backup loss and identical old/new digests remain blocked.
- HTTP protocol exceptions at request, manifest, checksum and executable boundaries; existing partial-file cleanup remains intact.
- Corrected authoritative-checksum fixture reaches checksum validation instead of failing on its workspace path.

Independent command:

```text
build/release-venv/Scripts/python.exe -m pytest -q tests/test_performance.py tests/test_updater.py tests/test_update_install.py --basetemp <new build/independent-review-UUID>
124 passed in 4.09s
```

Native filesystem operations affected only disposable workspace fixtures. Registry, services, power plans, HTTP and executable launches were mocked by the test suite. The run left the tool sandbox to permit already-authorized NTFS fixture operations; it did not execute real host maintenance. No full suite or native GUI run was started concurrently with the coordinator.

Limitations retained: real protected-directory ACL creation, running-image locks, frozen helper execution, physical reboot/power loss, different elevation contexts, exact real service/registry/power effects, and interrupted recovery require an authorized disposable Windows environment. The backend's readiness acknowledgment proves startup was reached, not later application health. The existing pending-state preservation policy can require manual recovery after a hard interruption; this review did not broaden that policy.

## ZEROfilez stable endpoint

Read-only checks used the connected GitHub tool and HTTPS requests. No catalog or release was changed.

- Current [ZEROfilez main `js/data.js`](https://github.com/falker47/ZEROfilez/blob/main/js/data.js) includes `name: Panacea`, `icon: ICONS.panacea`, and the exact URL `https://github.com/falker47/Panacea/releases/latest/download/Panacea.exe`.
- [`js/array.js`](https://github.com/falker47/ZEROfilez/blob/main/js/array.js) includes `panacea` in PC programs; [`js/pc-categories.js`](https://github.com/falker47/ZEROfilez/blob/main/js/pc-categories.js) includes it in Essentials.
- The [deployed catalog source](https://falker47.github.io/ZEROfilez/js/data.js) returned **HTTP 200** and the same stable URL, name and icon. This verifies deployed source data; no browser UI flow was exercised by this review.
- A HEAD request to the [stable executable endpoint](https://github.com/falker47/Panacea/releases/latest/download/Panacea.exe) returned **HTTP 200**, final host `release-assets.githubusercontent.com`, `Content-Length: 22290919`, and `Content-Type: application/octet-stream`. **Executable bytes downloaded: 0.**
- The [current latest release manifest](https://api.github.com/repos/falker47/Panacea/releases/latest) reports public stable **v1.47**, published 2026-03-20, with `Panacea.exe` at the matching size. Its GitHub-reported digest is `67319fdeca35ba0e8e7cd36031c7098d42f3d535a8598935bd865c03fe77aab9`. This digest was read from metadata, not independently recomputed in this review.

The stable integration is already correct and needs no edit. The endpoint currently serves the existing public release; it is not evidence of V2 publication. After explicit release approval and publication, repeat final-asset download/checksum validation and both deployed catalog flows against V2.

The first network probe inside the tool sandbox failed DNS resolution and the web reader could not fetch the deployed JS. A read-only request outside that tool sandbox succeeded. No failure was treated as proof of an absent endpoint.

## Windows isolation capabilities

Read-only native CIM, service/module inventory and known executable-path checks returned:

| Capability | Observed state |
| --- | --- |
| OS | Microsoft Windows 11 Home, 64-bit, `10.0.26300` |
| Host | HP Victus 16-e0xxx, AMD Ryzen 7 5800H |
| Virtualization firmware | Enabled |
| Hypervisor present | True |
| VirtualMachinePlatform | Enabled (`InstallState=1`) |
| HypervisorPlatform | Disabled (`InstallState=2`) |
| Containers-DisposableClientVM / Microsoft-Hyper-V-All | No corresponding feature entries returned |
| WindowsSandbox.exe | Absent at the standard System32 path |
| Hyper-V management | No Hyper-V PowerShell module; `vmms` not returned |
| Runtime services | `HvHost` and `vmcompute` running |
| VirtualBox / VMware | No `VBoxManage.exe` or `vmrun.exe` at checked standard installation paths; no matching command discovered |

Microsoft's [Windows Sandbox documentation](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/) explicitly says Home edition is unsupported. A present hypervisor/runtime service does not establish a usable sacrificial Windows guest. Processor CIM extension flags reported false while a hypervisor was active; they are recorded as observed and are not used to conclude that the hardware lacks virtualization.

No Sandbox/VM was launched, enabled, installed or changed. The probe does not rule out an unregistered/custom-path or remote VM; none was identified or authorized for use. Initial CIM access inside the tool sandbox was unavailable, so the same read-only queries were repeated outside it.

## Single remaining authorization checkpoint

The user must designate an existing disposable Windows guest, or explicitly authorize provisioning one using a chosen hypervisor and valid Windows image/license. That authorization must permit **guest-only** cleanup, Turbo/service/registry/power changes, network reset, restore-point/Resurrection execution, old-version updater migration, interruption/rollback tests and any required guest restarts. This does not authorize those operations on the host. Host hypervisor installation/feature enablement or host restart, if required by the chosen provisioning route, requires explicit scope as well.

Release publication, `latest` movement and final merge remain separate human approval gates after the verification gates pass.

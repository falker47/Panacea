# Diagnosing the 2.0.2 → 2.1.0 update

The message “Release page is outside the configured repository” is emitted by
`UpdateClient._validate_release`, before fetching the checksum, downloading the
EXE or starting a helper. In 2.0.2 it means the hostname, owner/repository or
`releases/tag/` route in the manifest's page URL failed validation. The tag
itself and asset URLs have separate checks and errors. A failed check cannot
replace the installed file.

## Identify the copy on the affected PC first

Use the shortcut's **Open file location** / target to identify the Panacea.exe
that showed the error. Download [Get-PanaceaUpdateDiagnostic.ps1](../../scripts/Get-PanaceaUpdateDiagnostic.ps1)
and run it from its folder under the normal Windows account:

```powershell
.\Get-PanaceaUpdateDiagnostic.ps1
```

Select that specific executable. The script reads its path, file version (which
can be empty), size and SHA-256, and independently queries public GitHub metadata.
It prints JSON to the console; it does not launch, install, update or upload
anything. Use `-Offline` to skip the request. Share the JSON after reviewing the
path. A hash match identifies a published EXE; a mismatch alone does not tell
us what created that file. This is a *current*, independent request, not the
historical response the application saw. Collect this evidence **before**
manual recovery.

## Manual recovery of the installed application

On the affected PC, close Panacea. From the official
[v2.1.0 release](https://github.com/falker47/Panacea/releases/tag/v2.1.0)
download **PanaceaSetup.exe**. From its download folder:

```powershell
(Get-FileHash -Algorithm SHA256 -LiteralPath .\PanaceaSetup.exe).Hash
```

Continue only for `E60BC29B12B3E4016F891E1E231689B8D82D2C1F6C788A291EB869E1833B9509`.
For the standard installation in `%ProgramFiles%\Panacea`, run Setup normally
and approve the Windows prompt. The installer uses the original per-machine AppId
but does **not** reuse a custom directory (`UsePreviousAppDir=no`). If the previous
installer used a custom protected directory under Program Files, an administrator
must explicitly pass that same verified path via Inno Setup's `/DIR=` option.
Do not select a user-writable or portable directory for an elevated installation. After installation the selected
`Panacea.exe` should match
`684121592593afd16042fceab7b6027bf81718aab276fc024ae6d6bf5baf056c` and open
as 2.1.0. This route does not require the old updater. For a portable copy,
Setup is a separate installation; it does not repair an arbitrary portable path.

## Reproduce on disposable Windows

The **Published updater recovery** workflow tests these historical published bytes
with a live unauthenticated request to `releases/latest`. It is expected to stop
being applicable after latest moves past 2.1.0. Do not run the protected probes
on a personal PC. Each job installs the pinned 2.0.2 Setup into an initially absent
Program Files directory on a fresh VM and check its installed EXE against the
official portable hash
`e390d2f26f84e108c0e076d834f61927554a77175fe19c22108667f04ec1161f`.

The helper job compares packaged 2.0.1 and 2.0.2 discovery with the live API.
It then clicks the uniquely matched **Install update** label in the real 2.0.2
window and confirms only that process's **Install verified update** dialog. The
label reference comes from the pinned English EXE on the Windows runner at 100%
DPI. A different UI fails closed. Panacea itself downloads, verifies and starts
the frozen helper; the probe observes the helper status, old GUI exit, installed
SHA-256 and visible Qt window. It also checks that 2.1.0 no longer offers itself. The manual jobs run the official 2.1.0 Setup over the previous installation,
using the default directory in one VM and an explicit protected custom directory
in another. Both check the AppId, executable hash and packaged restart.
The regular Windows integration jobs cover failed-launch rollback, readiness and
bad digest rejection. Neither a runner nor a fixture establishes which binary or
network response was present on the affected PC; interactive UAC and abrupt power
loss require separate physical evidence.

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
Run Setup normally, review the location and approve the standard Windows prompt.
The installer uses the existing per-machine AppId. After installation the selected
`Panacea.exe` should match
`684121592593afd16042fceab7b6027bf81718aab276fc024ae6d6bf5baf056c` and open
as 2.1.0. This route does not require the old updater. For a portable copy,
Setup is a separate installation; it does not repair an arbitrary portable path.

## Reproduce on disposable Windows

The **Published updater recovery** workflow tests these historical published bytes
with a live unauthenticated request to `releases/latest`. It is expected to stop
being applicable after latest moves past 2.1.0. Do not run the protected probes
on a personal PC. The two jobs each install the pinned 2.0.2 Setup into a unique
Program Files directory on a clean VM and check its installed EXE against the
official portable hash
`e390d2f26f84e108c0e076d834f61927554a77175fe19c22108667f04ec1161f`.

The helper job compares packaged 2.0.1 and 2.0.2 discovery with the live API,
downloads using 2.0.2's packaged client, and invokes the real frozen 2.0.2 helper
with a protected job while the original GUI stays open. The helper independently
checks GitHub, verifies and swaps the image, and waits for Qt readiness.
The probe supplies the job in place of clicking the confirmation dialog. The manual
job runs the official 2.1.0 Setup over the previous installation, without setting
a new destination, then checks the AppId, executable hash and packaged restart.
The regular Windows integration jobs cover failed-launch rollback, readiness and
bad digest rejection. Neither a runner nor a fixture establishes which binary or
network response was present on the affected PC; interactive UAC and abrupt power
loss require separate physical evidence.

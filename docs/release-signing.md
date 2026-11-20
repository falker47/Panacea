# Windows release signing

Release preparation accepts an optional Authenticode credential. With all three repository secrets absent, the build logs an unsigned notice and generates the usual SHA-256 manifests. A partial configuration fails the build.

| GitHub Actions secret | Value |
| --- | --- |
| `PANACEA_SIGN_PFX_BASE64` | Base64 encoding of a password-protected PFX containing the code-signing key and certificate chain. |
| `PANACEA_SIGN_PASSWORD` | PFX password. |
| `PANACEA_SIGN_TIMESTAMP_URL` | HTTPS URL of the signing provider’s RFC 3161 timestamp service. |

The workflow runs the Windows SDK’s x64 SignTool directly. Any issuer and timestamp service compatible with this PFX flow can be used. The signing steps receive the secrets only during release preparation. The workflow checks the reviewed commit belongs to main before running its code. Real signing requires a GitHub-hosted Windows runner on main. The temporary PFX lives under `RUNNER_TEMP` and is removed when signing exits. Using the PFX directly avoids importing a certificate into a store.

1. Build the one-file executable. Sign it using SHA-256 file and timestamp digests and verify it with `signtool verify /pa`.
2. Hash the verified executable into `Panacea.exe.sha256`. Inno checks that exact digest before embedding the executable.
3. Sign and verify the finished installer. Regenerate `PanaceaSetup.exe.sha256` from its final bytes. A signing or verification error stops the workflow before artifact upload.
4. The draft receives `Panacea.exe` first, followed by its checksum, the installer and the installer checksum.

PR CI exercises both finalization steps in dry-run mode without access to signing keys. Fixture tests cover absent credentials, partial configuration, the SignTool arguments, verification failure and the digest after signing. The updater test uses a synthetic PE certificate-table record and verifies the SHA-256 digest over the entire file. A trusted Authenticode chain requires a credentialed release build.

The Windows SDK reference documents PFX selection, RFC 3161 timestamps and the default Authenticode verification policy. [Microsoft SignTool reference](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)

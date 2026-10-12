# Integrated safety verification

Candidate 1.49.0; host Windows 11 build 26300, Python 3.14.3. This is a source audit, independent reviews and fixture verification, not a completed Codex Security managed scan or a certification.

## Opened-object boundary

The original guard's deny-write sharing was insufficient: FILE_WRITE_ATTRIBUTES (0x100) permitted in-place FSCTL_SET_REPARSE_POINT on an empty guarded directory. Native regressions reproduced outside-fixture enumeration/counting and deletion before the final correction. All paths were disposable fixtures; no host maintenance or user-data deletion occurred.

Cleanup now binds every opened object to the immutable approved DOS path using normalized GetFinalPathNameByHandleW, refuses reparse points and unverifiable identities, and checks directory case sensitivity. It never derives approval with realpath after a retarget. Live directory checks bracket enumeration and Firefox discovery; file metadata/counting and disposition use the validated handle. Deny-write/delete sharing protects data changes and entry renames, but is not claimed to prevent every attribute mutation. Hardlinks, ambiguous namespaces, mismatching aliases and case-sensitive directories fail closed. Unavailable native identity/case queries also fail closed.

Turbo shares this boundary. Snapshot reads use the validated file handle; exclusive temporary creation and missing-directory creation are relative to the retained parent object with NtCreateFile. The same owned file handle persists through payload write, flush, atomic same-parent rename and failure disposition. No pathname unlink can remove a replacement entry during exception cleanup. The recovery snapshot is durable before settings may change. Global transaction mutex/reload behavior and exact original-state restoration remain intact.

Native regressions cover eight reparse access masks, retarget during enumeration/Firefox discovery, existing/missing Turbo directories, retarget immediately after parent validation, snapshot read redirection, write failure, collision and ordinary mixed-case names. Legitimate controls cover nested counts, preview, locked files, hardlinks, browser Bookmarks, restart restoration and competing/abandoned processes.

## Fresh review: case-sensitivity hypothesis

The fresh candidate reviewer proposed a case-folding escape by enabling case sensitivity on a held ancestor containing Temp, creating a distinct temp sibling and redirecting Temp there. The reviewer explicitly left the native precondition unverified. Parent execution confirmed that SetFileInformationByHandle(FileCaseSensitiveInfo) rejects enabling the flag on that nonempty ancestor with ERROR_DIR_NOT_EMPTY (145), in both preview and deletion timing. Its continuously held child cannot be renamed/deleted to make the ancestor empty. A separate empty-directory control successfully enables the flag and is then refused by cleanup. The proposed route did not reproduce; it was not treated as a fixed vulnerability or used to justify an unrelated redesign. Two regressions retain the native precondition.

Sources: [sharing rules](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), [normalized final paths](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew), [relative native creation](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntcreatefile), [same-parent rename](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information), [case-sensitivity constraints](https://learn.microsoft.com/en-us/windows/wsl/case-sensitivity).

## Other reviewed boundaries

- Commands resolve allowlisted native tools through the system directory, pass explicit argv and shell=False; startup metadata queries do the same.
- Restore creation requires a verifiably advanced sequence and never enables protection implicitly. Resurrection stops on that critical prerequisite and retains individual failed/partial/cancelled results.
- Updater selects the exact official asset and separate SHA-256, bounds downloads and validates HTTPS provenance, length, digest and PE headers before replacement. Protected installation, readiness, retained backup, rollback and completed-marker recovery are fixture-tested. Portable user-writable locations receive the manual alternative.
- UAC, copied-helper and new-target frozen relaunches request independent onefile extraction with the public PYINSTALLER_RESET_ENVIRONMENT=1 variable. Private bootloader variables are preserved. Packaging pins PyInstaller 6.22.3 and rejects older toolchains. [The 2026 advisory](https://github.com/pyinstaller/pyinstaller/security/advisories/GHSA-9fxf-4qw3-ghmr) affects versions below 6.22.1; [supported restart environment](https://pyinstaller.org/en/stable/advanced-topics.html#public-environment-variables) documents independent restart behavior.

## Ordered verification

| Check | Result |
| --- | --- |
| Original attribute-conversion reproductions before patch | RED: three cleanup and three Turbo cases |
| pytest tests/test_cleanup.py tests/test_performance.py --basetemp build/tests-binding-completed -q | 53 passed |
| pytest tests --basetemp build/tests-final-monitor-lifecycle -q | 231 passed; no skips or failures, including frozen v1.47 detection excerpt and native owned-process/timeout fixtures |
| Ruff; compileall main/UI/version/modules/scripts; imports | Passed |
| Isolated PyInstaller 6.22.3 build; PE/name/version/checksum; real EXE --smoke-test | Passed; candidate-package.json |

An earlier integrated invocation had one transient Tk library-read failure (217 passed, one failed). The file existed, the isolated 20-test GUI suite passed, and the fresh integrated run passed without disabling or changing GUI tests. The cause was not established; this observation is retained. CI must independently validate Python 3.12 on its Windows runner.

## Release proof gaps

Actual OS DPI changes, interactive UAC, real protected-directory helper installation, running-image migration from v1.47, crash/readiness recovery and sensitive maintenance on representative Windows 10/11 require an expressly authorized disposable environment. Fixtures and safe EXE startup do not prove those gates. No Authenticode certificate is available, so the candidate is unsigned. Stable publication still requires these checks, green candidate CI and final human approval.

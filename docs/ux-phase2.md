# Panacea — UX phase 2 QA specification

Scope: feedback received 2026-10-26; implemented on the existing draft PR #4,
with no changes to published `main` or `v2.0.0` release.

## User-facing changes

- Overview explicitly calls the metric **Memory (RAM)**.
- The first Cleanup card contains **Quick cleanup**: one explicit
  irreversible-deletion confirmation covers three serial native operations
  (eligible Temp files, entire Recycle Bin, DISM superseded components).
  After all three steps have returned with verified command completion,
  Panacea **opens** Windows Disk Cleanup as a separate, user-controlled task;
  it does NOT select categories or assert that Windows cleanup was completed.
  A failed, skipped, partially successful, cancelled or unknown result remains
  visible and is never described as a fully successful run.
- Individual cleaning actions, including read-only Temp analysis, remain
  available through **Show individual tools** and retain their own guards,
  output, consent requirements and diagnostics.
- Sidebar branding and navigation are larger with more breathing room. The
  full original Panacea logo is unchanged; only the navigation icon is the
  actual chalice isolated and tinted like the other outlined glyphs.
- Each Guided Maintenance phase has an optional inline explanation that can
  also show its actual execution result; the ten existing steps and their
  completion logic are untouched.

## Risk boundaries

No automatic or unconfirmed cleanup on startup. Bulk deletion is irreversible
and a System Restore checkpoint does not restore deleted files. The new
sequence calls existing conservative managers; the component-store command
keeps the existing trusted allowlist, process timeout and persistent
uncertain-completion guard. A close request cancels between steps; it does not
interrupt an active Windows servicing command. This QA build must not be used
for destructive testing on a non-disposable Windows installation.

## Acceptance criteria

- `Memory (RAM)` and five legible primary navigation destinations.
- Quick cleanup is primary; individual actions expand and remain usable.
- A denied confirmation launches no worker or Windows operation.
- Actual three-step order, counters, partial/errors, and restart/unknown
  feedback are correct. Disk Cleanup launch is clearly labeled manual.
- Expandable per-phase explanatory text and original brand logo preserved.
- CI passes all tests, Windows smoke and isolated installer exercises.
- Human Windows visual QA (including 1366×768 at 150% scaling) precedes merge.

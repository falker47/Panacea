# Panacea — UX iteration 3 (26 October 2026)

Implemented only on the existing draft PR #4; the published release stays at v2.0.0.

- Sidebar retains the original image and approved tinted Guided Maintenance chalice.
  The original brand icon is 68px (was 61), title 28px (was 24), tagline 11px
  semibold (was 9); sidebar width 260px, navigation icons 31px, labels 15px
  Segoe UI Semibold, with slightly more vertical breathing room and Title Case.
- Space & Cleanup keeps the icon-free Quick cleanup card and its original
  guarded, serial three-step implementation followed by manual Windows Disk
  Cleanup launch. No backend maintenance commands or confirmations changed.
- Expanded individual tools present exactly four actions: Delete temporary files,
  Recycle Bin, Component store, Windows Disk Cleanup. The large optional
  temporary-file analysis card (including duplicate icon, Analyze, View reasons)
  is no longer rendered. The read-only temporary analysis backend and Overview
  preview remain available and preserve their diagnostic snapshots.
- Geometry regression verifies logo/text, sidebar labels/icons, footer baseline,
  resizing and cleanup controls at 1366x768 and 1920x1080, 100/125/150% UI scaling.
  No additional dependencies.

## QA gate

Run Windows CI, packaged executable smoke and isolated Windows/installer probes.
Then inspect the portable QA executable at 1366x768 / 150% scaling and at normal
desktop scaling. Confirm branding and navigation are fully readable without
overlap or footer clipping, and individual cleanup reveals only four operations.
Do not execute destructive cleanup on a personal Windows machine during visual QA.
No stable merge or release before human acceptance.

# Panacea 2.0.0 final polish

The user's final polish brief is the approved scope and execution authorization.
Continue PR #3 on `feat/panacea-brand-dashboard-20261013`; keep version 2.0.0.

1. Establish live clean baseline and run existing tests (443 passed).
2. Preserve one-pass native cleanup and add evidence-based skip categories,
   original diagnostics, progressive optional analysis and isolated regressions.
3. Implement two independent temporary-file actions. Analysis is read-only and
   reports potential recovery; confirmed direct cleanup reports actual deletion.
   Changed filesystem contents are rechecked by the existing guarded traversal.
4. Keep a per-panel open state. Accepted explicit operations open their output
   once; messages never reopen it. Views and results survive navigation. Add
   controller coverage for refusal, concurrency, failure and partial results.
5. Refine sidebar footer/brand, three Dashboard icons and the Cleanup analysis
   card; validate native geometry and keyboard behavior at both requested sizes
   and three simulated CTk scales. Actual Windows DPI remains an open gate.
6. Run targeted tests, full suite, lint and compilation. Capture native screenshots
   and clearly labeled inert operation fixtures. Build a separate 2.0.0 candidate
   and verify packaged launch, hash, size and source identity.
7. Review changes, commit/push, obtain final Windows CI and update existing PR #3.

Review focus: optional analysis cannot authorize deletion; direct cleanup must not
pre-scan; locked/changed objects keep native safeguards; partial/error states must
not claim success; manual output collapse must survive worker messages. Do not
perform host maintenance, migration, UAC/rollback exercises, merge, tag or release.

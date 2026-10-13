# V2 performance and executable checks

Measured 2026-10-13 on the same Windows 11 Home build 26300 machine, Python
3.14.3, using the same checked-in harness for the baseline and candidate.
Baseline source was extracted from exact commit `24e2ade`; candidate source
matches `v2-candidate-manifest.json`. No maintenance or cache purge was run.

| Read-only source measurement | Baseline | V2 candidate |
| --- | ---: | ---: |
| Median ready time, five fresh processes | 0.9943 s | 0.9467 s |
| Median first metric | 0.7775 s | 0.7279 s |
| Event-loop delay p95 | 16.63 ms | 18.24 ms |
| Maximum observed delay | 263.34 ms | 224.05 ms |
| Median normalized idle CPU | 0.000% | 0.048% |
| Median idle working set | 58.37 MiB | 59.98 MiB |

The five-process source measurements use direct import/constructor plus event
loop readiness, excluding UAC/splash and PyInstaller extraction. Each process
observes five seconds. Idle measurements use ten one-second intervals after a
ten-second settle, Windows process times normalized by logical CPU count, and
native working-set memory. Background monitoring remains enabled.

These are small samples from a shared, busy desktop with uncontrolled cache,
scheduling and network conditions. V2's observed median startup is 48 ms lower,
p95 event delay 1.61 ms higher, and working set 1.61 MiB higher. These differences
do not establish a repeatable speedup or regression. No subjective performance
claim substitutes for the raw data.

Raw evidence: [baseline startup](v2-baseline-startup.json),
[candidate startup](v2-candidate-startup.json),
[baseline idle](v2-baseline-idle.json), [candidate idle](v2-candidate-idle.json).

The separate [packaged probe](v2-candidate-packaged.json) launches the final
local `Panacea.exe --smoke-test` five times, verifies a visible native client
window of at least 640×400 belonging to that executable, records startup and
exit, and binds the result to the EXE SHA-256. It includes one-file extraction;
its timings are not compared with the source-only baseline. Safe smoke bypasses
UAC and closes automatically without maintenance. It does not establish normal
elevated startup, running-image update replacement or rollback.

Reproduce with the existing development environment:

```powershell
python scripts/benchmark.py --source build/v2-baseline-source --label v2-baseline
python scripts/benchmark.py --label v2-candidate
python scripts/idle_probe.py --source build/v2-baseline-source --output docs/validation/v2-baseline-idle.json
python scripts/idle_probe.py --output docs/validation/v2-candidate-idle.json
python scripts/packaged_probe.py --exe dist/v2.0.0/Panacea.exe --output docs/validation/v2-candidate-packaged.json
```

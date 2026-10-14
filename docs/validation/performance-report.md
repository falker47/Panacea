# Final source performance evidence

Date: 2026-10-12. Candidate: 1.49.0. Product UI is frozen.

## Method and scope

The command is `build/release-venv/Scripts/python.exe scripts/benchmark.py --label final-validated --samples 5`. It launches five fresh source processes through scripts/gui_probe.py, measures direct PanaceaApp import/construction and event-loop readiness with perf_counter, records the first displayed CPU/RAM/disk sample and samples 50ms event-loop heartbeat delay for five seconds per process. Read-only system monitoring and update discovery remain enabled. No cleanup, repair, Turbo mutation, UAC or updater installation is invoked.

Environment for both retained baseline and current run: Windows-11-10.0.26300-SP0, Python 3.14.3, same host. The final run uses the isolated build/release-venv Python, whose version matches the valid baseline. Baseline windows are 900x560; the redesigned default windows are 1020x680. This is equivalent product-startup methodology, rather than identical layout dimensions. The source benchmark excludes main.py UAC/splash handling and PyInstaller extraction, so it must not be described as packaged startup or an end-to-end EXE launch measurement.

The prior-release source's first dashboard callback waited for RAM/disk metadata. The redesigned app displays the native fast metric sample independently and loads secondary hardware metadata in its own worker. Both hooks therefore measure when core resource usage becomes readable; the changed hook intentionally captures the new user-visible readiness contract.

Raw baseline: [before-startup.json](before-startup.json). Current summary and all five raw heartbeat arrays: [final-validated-startup.json](final-validated-startup.json). Individual process outputs: build/validation/final-validated-sample-0.json through final-validated-sample-4.json.

## Five-sample comparison before the final query-shutdown correction

The controller confirmed that the isolated PyInstaller build and smoke test were complete before this final repeat began. No build or tests ran concurrently. All five source processes completed successfully, with usable 1020x680 windows. The earlier exploratory run remains preserved as [final-validated-prebuild-startup.json](final-validated-prebuild-startup.json); the final-validated summary and individual sample files now contain the post-build repeat.

| Measurement | Valid baseline | Current source | Change |
|---|---:|---:|---:|
| Median window readiness | 1.238126 s | 0.864890 s | 30.1% lower |
| Median first core metric | 3.305327 s | 0.658503 s | 80.1% lower |
| Heartbeat delay p95 | 13.643100 ms | 13.461000 ms | 1.3% lower; effectively similar |
| Worst heartbeat delay | 229.091500 ms | 194.309500 ms | 15.2% lower in this cohort |

| Sample | Baseline ready (s) | Baseline metric (s) | Current ready (s) | Current metric (s) |
|---|---:|---:|---:|---:|
| 1 | 1.238126 | 3.392416 | 0.804819 | 0.634680 |
| 2 | 1.196369 | 2.955643 | 0.858489 | 0.642973 |
| 3 | 1.189133 | 3.232042 | 0.864890 | 0.713756 |
| 4 | 1.317113 | 3.470632 | 0.905124 | 0.686215 |
| 5 | 1.263834 | 3.305327 | 0.901808 | 0.658503 |

The median results support faster source readiness and faster access to core metrics on this host. The final heartbeat p95 remains close to baseline; a large general responsiveness improvement is not supported. The pre-build cohort measured p95 1.455500ms and maximum 351.399900ms, including a slower second startup sample. Those observations are retained rather than discarded. The difference between cohorts is a reason to avoid a strong tail-latency claim. Host workload and caches were not frozen, so the percentages are observations of these samples, not guaranteed speed improvements on other machines.

## Intermediate source idle measurements

Existing [before-idle.json](before-idle.json) and [after-idle.json](after-idle.json) measure the source GUI process alone over ten one-second intervals after a ten-second settle. GetProcessTimes CPU is normalized by logical processor count; GetProcessMemoryInfo provides working set. Monitoring/background checks remain active and no maintenance runs. Child processes, including PowerShell queries, are excluded.

These files were measured before the final cleanup-boundary edits. They are **intermediate idle evidence**, not final-candidate or packaged resource measurements.

| Process-only intermediate measurement | Before | After | Interpretation |
|---|---:|---:|---|
| Median working set | 85.609375 MiB | 82.925781 MiB | 2.683594 MiB / 3.1% lower in the recorded interval |
| Median normalized CPU | 0.000% | 0.000% | Below timer resolution in the median interval; no zero-cost or CPU-improvement claim |
| Highest recorded normalized CPU interval | 0.289935% | 0.871844% | Nonzero bursts remain; excludes child-process CPU |

The JSON key working_set_mb contains the reported binary MiB values. Neither a zero median CPU delta nor this process-only working set describes total resource use of the application and its child queries.

## Packaged candidate startup

The final local Windows binary was built with isolated PyInstaller 6.22.3 and Python 3.14.3. Five sequential fresh `--smoke-test` launches all exited0 and produced a native visible client area1020x680. `scripts/packaged_probe.py` observed the first visible usable-sized window every20ms; median was1.906254s, individual values2.098890/1.919202/1.906254/1.799750/1.700776s. This includes onefile extraction and excludes UAC. Fixed1.5s smoke observation affects total runtime but not mapped-window time. No OS cache purge was performed; these are sequential cached-environment samples, not a controlled cold/warm experiment. [Raw package samples](packaged-startup.json).

The binary is24,204,263 bytes,8.6% larger than published v1.47's22,290,919 bytes. Runtime/toolchain and functionality differ, so this is an artifact-size comparison, not a controlled optimization claim. The prior EXE was downloaded/hash-verified but never executed on the host. [Candidate identity](candidate-package.json).

## Final query-shutdown revision

The final correction tracks/cancels only owned read-only monitor queries and closes their pipes. Older cohorts remain retained at their measured revisions. A fresh equivalent five-sample source run after the final build, without parallel build/capture work, is [release-final-startup.json](release-final-startup.json): median readiness 0.894027s versus baseline 1.238126s (27.8% lower), first core metric 0.698827s versus 3.305327s (78.9% lower), heartbeat p95 13.6925ms versus 13.6431ms (similar), maximum 160.7414ms versus 229.0915ms. Readiness is the shared 150ms event-loop observation after construction; first metric is GUI metric-callback entry, not a separate paint-completion measurement. Both original hooks share this scope.

The final local package is 24,206,497 bytes with SHA-256 6b40342a235824b4f368a4c2c8d131fa53c16385209b0317e82021c5228776d3. All five new safe EXE launches passed with 1020x680 native visible client areas; median mapped-window time 1.852121s. [Raw final package samples](release-final-packaged-startup.json). These sequential samples retain the cache/UAC limits of the earlier package cohort. The current package remains unsigned. Real prior-version migration and true OS DPI are pending.

## Limits

- Final-candidate and packaged per-process CPU/memory were not measured by this task; only the separately labeled intermediate idle data are available. Dashboard host resource usage in screenshots is not application-memory evidence.
- Controlled cold/warm packaged startup, true Windows DPI changes, safe VM maintenance and prior-release update migration remain unverified.
- Artificial splash-delay removal is excluded by the shared source harness and is not credited for these numbers.
- Metadata completion timing was not measured by this benchmark; populated final dashboards provide visual correctness evidence only.
- A longer controlled test would be needed to characterize heartbeat tails and the observed between-cohort variation.

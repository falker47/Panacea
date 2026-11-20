# Panacea 2.2 Windows package and startup

The T2 Windows one-file build is **51,060,081 bytes**, down **121,367,839 bytes (70.4%)** from the published v2.1.1 executable. The release spec retains Pillow, Basic Controls, Effects, Qt SVG and the software OpenGL fallback. The embedded PE product version is 2.1.1.

| Build | EXE bytes | Archive entries | Stored bytes | Uncompressed bytes |
| --- | ---: | ---: | ---: | ---: |
| Published v2.1.1 (release inventory supplied for T2) | 172,427,920 | 2,793 | ≈171.8 MB | ≈431.5 MB |
| T2 local candidate | 51,060,081 | 271 | 50,670,137 | 127,121,693 |
| T2 throwaway build with PIL excluded | 43,740,302 | 263 | 43,350,822 | 113,055,334 |

The size gate uses decimal MB. It sums the CArchive uncompressed lengths, including embedded Python code, as a conservative bound on extraction. The two T2 builds used the same Windows x64 host, CPython 3.12.10, PySide6 6.10.2, PyInstaller 6.22.3 and spec. The measurement copy added only `PIL` to Analysis exclusions. Its output is for size comparison only. Candidate SHA-256 was `0b38bbbf8a538b764891c41256f3fddf2bad2f7524bebafb6db3eb0948bcb21c`.

## Time before the event loop

Five fresh local launches used the packaged candidate, Qt offscreen with the software renderer, the Basic style and disabled QML disk cache. Each launch rendered a different tab using the smoke fixture. All five PNGs were nonempty, all five metadata records contained zero QML warnings, and frozen backend imports passed.

| Interval | Median | Measurement boundary |
| --- | ---: | --- |
| Launch to first Python lifecycle log | 1,388 ms | Parent monotonic clock, polling for creation every 5 ms. Range 1,247–1,971 ms. Includes one-file extraction, process startup, interpreter initialization and initial Python imports. |
| Qt imports | 37.6 ms | First Python trace through completion of Qt imports |
| Remaining imports and startup code before creating QGuiApplication | 131.5 ms | End of Qt imports to the application creation trace |
| Bridge creation and setup after QGuiApplication | 12.9 ms | Application created to bridges created |
| QML load | 276.4 ms | Immediately before and after `engine.load`, loading the initial shell |
| First Python trace clock to event-loop entry | 477.0 ms | Includes the in-process phases above |

The first interval is an upper bound on extraction alone. PyInstaller extracts the one-file payload before the child initializes Python. The native, visible-window comparison against v2.1.1 is a separate hosted measurement. [PyInstaller boot sequence](https://pyinstaller.org/en/stable/advanced-topics.html#bootloader)

Five source-mode offscreen runs under `-X importtime` yielded cumulative medians of **58.6 ms** for `qt_app.icon_provider`, **35.2 ms** for its `modules.ui_icons` import, **15.9 ms** for `PIL.Image` and **20.4 ms** for `qt_lab.main`. The first three timings are nested. Source import timing includes instrumentation overhead and has a different loader from the frozen build.

## Follow-up by measured cost

1. Once T3 removes the last runtime Pillow import, T6 can apply the tested exclusion and repeat the packaged captures. It saved **7,319,779 executable bytes** and **14,066,359 uncompressed bytes**. The existing icon provider still needs Pillow on T2.
2. Keep the software OpenGL fallback for this build. It contributes **7,660,531 stored bytes** and **20,639,544 uncompressed bytes**. Removing it needs a separate GPU-less hosted smoke and capture of the exact build that omits it.
3. Measure lazy creation of the initial QML view when T3 integrates the shell. QML load took **276.4 ms** of the **477.0 ms** median to event-loop entry. Moving the shared MetricsBridge out of the lab entry module is a smaller experiment with a **20.4 ms** source import baseline. Remeasure both against the integrated shell before changing readiness scheduling.
4. Keep the Windows DLL search path scoped to System32, Windows and the selected interpreter during Analysis. An initial build collected an unrelated ICU distribution from the host PATH. Its `icuuc.dll` lacked 20 unversioned imports requested by Qt6Core and the candidate stopped at the first Qt import. The corrected package loaded Qt and passed every offscreen capture.

## Hosted evidence for the reviewed commit

The CI packaged-performance artifact contains `bundle.json` with entry sizes and the twenty largest compressed entries, per-tab capture metadata, `package-sizes.json`, and `packaged.json`. The startup probe hashes the official v2.1.1 download before launching either binary. It alternates sample order and measures five fresh launches of each executable on the same runner. The gate uses the medians to a visible client window of at least 640 × 400 pixels. It reports the GUI process and bootloader working-set high-water marks separately. OS filesystem caches stay enabled.

The protected installer artifact records seconds from before process creation to the first observed matching token with `ready=true`. The polling interval is 10 ms. The limit is 15 seconds and the subsequent cleanup gate still requires the marker and backup to disappear. These hosted results are pending until a same-repository PR runs the three Windows CI jobs.

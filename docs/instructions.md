# Historical design brief

This file preserves the **initial v1 design direction** for Panacea. It is not the authoritative specification for the current application.

The project subsequently evolved beyond several constraints in the original prompt. In particular, current Panacea includes:
- selected Windows service start/stop controls;
- a documented `VisualFXSetting` registry change;
- browser-cache cleanup;
- an automated multi-step maintenance protocol;
- a GitHub Releases self-update path.

For current behavior, safety boundaries, build instructions and verification scope, use the repository root [README](../README.md) and inspect the implementation under `modules/` and `panacea_ui.py`.

## Original design goals

The first version was intended as a small Windows desktop utility for:
- temporary-file cleanup;
- Recycle Bin cleanup;
- native disk optimization;
- selected SFC/DISM repair commands;
- DNS/Winsock reset;
- administrator-elevation handling;
- operation logging.

The original safety principle was to prefer native Windows tools and avoid broad, opaque “optimizer” behavior. That principle remains useful, but the current implementation should be judged by what the code actually performs rather than by this historical brief.

## Historical validation targets

The initial brief called for manual validation on Windows 10 and 11 covering:
- UAC behavior;
- locked temp files;
- SSD/HDD optimization behavior;
- logging;
- command execution.

The current GitHub Actions workflow adds build/smoke verification, while elevated system-maintenance behavior still requires manual Windows testing.

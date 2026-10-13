"""Native GUI state fixtures. Every backend is inert before application init.

No maintenance, system query, network request, settings change or EXE launch is
performed by a capture child. A fresh process owns each native Tk interpreter.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import ExitStack


ROOT = Path(__file__).resolve().parents[1]
LABEL = 'SIMULATED RESULTS · UI fixture only'
CASES = {
    'cleanup-loading': ('Cleaning', 'loading', 'Pending inert preview; controls disabled.'),
    'cleanup-success': ('Cleaning', 'success', 'Synthetic successful preview; no deletion.'),
    'cleanup-partial': ('Cleaning', 'partial', 'Synthetic preview with skipped and locked entries.'),
    'cleanup-error': ('Cleaning', 'error', 'Synthetic preview exception and visible error feedback.'),
    'disk-unavailable': ('Disk', 'unavailable', 'Synthetic offline volume; optimization disabled.'),
    'turbo-unknown': ('Turbo', 'unavailable', 'Unknown settings and unavailable originals.'),
    'turbo-saved-partial': ('Turbo', 'partial', 'Two saved originals with incomplete live state.'),
    'resurrection-running': ('Resurrect', 'running', 'Two completed steps; third running; progress 2/10.'),
    'resurrection-completed': ('Resurrect', 'success', 'Ten simulated successful steps; progress 10/10.'),
    'resurrection-partial': ('Resurrect', 'partial', 'Synthetic network-reset failure; all ten attempted.'),
    'resurrection-failed': ('Resurrect', 'error', 'Synthetic restore-point failure; nine steps not run.'),
    'resurrection-cancelled': ('Resurrect', 'cancelled', 'Cancellation after two steps; eight not run.'),
    'dashboard-unavailable': ('Dashboard', 'unavailable', 'All synthetic resource samples unavailable.'),
}


class InertManager:
    def log(self, *args, **kwargs):
        pass

    def close(self):
        pass

    def __getattr__(self, name):
        raise AssertionError(f'Unconfigured fixture backend access: {name}')


class InertMaintenanceGuard:
    last_error = ''

    def is_blocked(self):
        return False

    def mark_unknown(self):
        raise AssertionError('Fixture must not persist maintenance guard records')


def denied(*args, **kwargs):
    raise AssertionError('Native maintenance/launch/network actions are forbidden in UI fixtures')


def source_hashes():
    names = ['panacea_ui.py', 'version.py', 'modules/ui_dispatch.py', 'modules/operations.py',
             'modules/ui_icons.py', 'scripts/ui_state_check.py']
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def fixture(ui, app, name, releases):
    """Apply real presentation/controller methods to explicit synthetic inputs."""
    app.select_frame(CASES[name][0])
    if name.startswith('cleanup-'):
        gate = threading.Event()
        releases.append(gate)
        app.cleanup_mgr.last_result = SimpleNamespace(errors=[], skipped=[])
        if name == 'cleanup-partial':
            app.cleanup_mgr.last_result = SimpleNamespace(
                errors=['Fixture only: one locked cache entry'], skipped=['Fixture only: protected entry'])
        def preview():
            if name == 'cleanup-loading' and not gate.wait(15):
                raise TimeoutError('Fixture preview was not released')
            if name == 'cleanup-error':
                raise PermissionError('Fixture only: temporary folder is unavailable')
            return 24, 3 * 1048576
        app.cleanup_mgr.preview_temp_files = preview
        app.run_preview_temp()
        def ready():
            return app.workers.busy() if name == 'cleanup-loading' else not app.workers.busy()
        def verify():
            text = app.preview_label.cget('text')
            status = app.operation_label.cget('text')
            if name == 'cleanup-loading':
                assert 'Scanning' in text and app.btn_clean_temp.cget('state') == 'disabled'
            elif name == 'cleanup-error':
                assert 'failed' in text.lower() and 'Failed' in status
            else:
                assert '24 files' in text and '3.0 MB' in text
                assert ('Partial' if name == 'cleanup-partial' else 'Completed') in status
                assert app.btn_clean_temp.cget('state') == 'normal'
            return {'preview': text, 'operation': status, 'delete_enabled': app.btn_clean_temp.cget('state')}
        return ready, verify

    if name == 'disk-unavailable':
        app._set_drives([{'letter': 'Z:', 'type': 'Fixed', 'available': False,
                         'total_bytes': None, 'free_bytes': None, 'used_percent': None,
                         'error': 'Fixture only: volume offline'}])
        def verify():
            assert app.btn_optimize_drive.cget('state') == 'disabled'
            assert 'Unavailable' in app.drive_detail.cget('text')
            return {'drive_detail': app.drive_detail.cget('text'), 'optimize_enabled': 'disabled'}
        return lambda: True, verify

    if name.startswith('turbo-'):
        states = dict.fromkeys(('power', 'visual', 'sysmain', 'wsearch', 'spooler'))
        saved = None
        if name == 'turbo-saved-partial':
            states.update(power=True, sysmain=False, spooler=False)
            saved = ('power', 'visual')
        app._apply_turbo_states((states, None))
        app._apply_saved_turbo(saved)
        def verify():
            assert app.master_switch.cget('state') == 'disabled'
            assert app.master_switch.cget('text') == 'Unknown'
            assert app.btn_restore_turbo.cget('state') == ('normal' if saved else 'disabled')
            for key, value in states.items():
                if value is None:
                    assert app.turbo_switches[key].cget('state') == 'disabled'
                    assert app.turbo_switches[key].cget('text') == 'Unknown'
            return {'live_settings': states, 'saved_originals': saved,
                    'recovery_text': app.turbo_saved_label.cget('text'),
                    'restore_enabled': app.btn_restore_turbo.cget('state')}
        return lambda: True, verify

    if name.startswith('resurrection-'):
        gate = threading.Event()
        releases.append(gate)
        app.cleanup_mgr.last_result = SimpleNamespace(errors=[], skipped=[])
        app.restore_mgr.create_restore_point = lambda description: (
            name != 'resurrection-failed', 'Fixture only: restore point response')
        def browsers():
            if name == 'resurrection-cancelled':
                app._resurrect_cancel.set()
            return 5, 1048576
        def temporary(**kwargs):
            if name == 'resurrection-running' and not gate.wait(15):
                raise TimeoutError('Fixture step was not released')
            return 7, 2 * 1048576
        app.cleanup_mgr.clean_browser_caches = browsers
        app.cleanup_mgr.clean_temp_files = temporary
        app.cleanup_mgr.empty_recycle_bin = lambda: (True, 'Fixture only: empty bin response')
        app.cmd_runner.restart_required = False
        app.cmd_runner.run_command_stream = lambda command, description, callback: not (
            name == 'resurrection-partial' and description == 'Network reset')
        app.disk_opt.analyze_optimize_drive = lambda *args, **kwargs: True
        for step in app.RESURRECTION_STEPS:
            app._set_resurrection_step(step, 'pending')
        def done():
            app.btn_resurrect_cancel.pack_forget()
            app.btn_resurrect_start.configure(text='Start sequence')
        assert app._request_operation('Resurrection', app._run_resurrection_sequence,
                                      app._finish_resurrection, done)
        app.btn_resurrect_start.configure(text='Maintenance running…')
        app.btn_resurrect_cancel.pack(side='left')
        expected_attempted = {'resurrection-running': 2, 'resurrection-cancelled': 2,
                              'resurrection-failed': 1}.get(name, 10)
        expected_status = name.removeprefix('resurrection-')
        def ready():
            if name == 'resurrection-running':
                return app._resurrection_states.get('Temporary files', ('',))[0] == 'running'
            return app.last_resurrection_result is not None and not app.workers.busy()
        def verify():
            assert abs(app.progress_bar.get() - expected_attempted / 10) < 0.001
            phases = {step: status[0] for step, status in app._resurrection_states.items()}
            if name == 'resurrection-running':
                assert app.workers.busy() and phases['Temporary files'] == 'running'
                assert sum(state == 'completed' for state in phases.values()) == 2
                assert app.btn_resurrect_start.cget('state') == 'disabled'
            else:
                result = app.last_resurrection_result
                assert result['status'] == expected_status
                assert len(result['steps']) == expected_attempted
                assert sum(state == 'not run' for state in phases.values()) == 10 - expected_attempted
                if name == 'resurrection-partial':
                    assert phases['Network reset'] == 'failed'
                    assert sum(state == 'completed' for state in phases.values()) == 9
                if name == 'resurrection-failed':
                    assert phases['Restore point'] == 'failed'
            return {'status': expected_status, 'attempted': expected_attempted,
                    'progress': app.progress_bar.get(), 'phases': phases,
                    'visible_phase_labels': {step: label.cget('text') for step, label in app._resurrection_rows.items()},
                    'summary': app.lbl_status.cget('text')}
        return ready, verify

    app._update_fast_gui({'ram': None, 'disk': None, 'cpu': None,
                         'uptime': 'Unavailable', 'battery': (None, 'Unknown')})
    app._update_metadata_gui({'os': 'Windows · UI fixture', 'cpu_name': '', 'ram_info': '', 'disk_model': ''})
    app._update_updates_gui(-1, -1, 'Unavailable · UI fixture')
    def verify():
        assert app.dash_cpu_val.cget('text') == '—'
        assert app.dash_ram_perc.cget('text') == '—'
        assert app.dash_disk_state.cget('text') == 'Unavailable'
        return {'cpu': app.dash_cpu_val.cget('text'), 'memory': app.dash_ram_val.cget('text'),
                'disk': app.dash_disk_state.cget('text')}
    return lambda: True, verify


def capture(args):
    sys.path.insert(0, str(ROOT))
    import customtkinter as ctk
    from PIL import ImageGrab
    import panacea_ui as ui
    errors, releases, observed = [], [], {}
    class DispatchErrors(logging.Handler):
        def emit(self, record):
            errors.append(record.getMessage())
    handler = DispatchErrors(level=logging.ERROR)
    logger = logging.getLogger('modules.ui_dispatch')
    logger.addHandler(handler)
    with ExitStack() as patches:
        for manager in ('Logger', 'CleanupManager', 'DiskOptimizer', 'CommandRunner',
                        'SystemMonitor', 'RestoreManager', 'PerformanceManager'):
            patches.enter_context(patch.object(ui, manager, InertManager))
        patches.enter_context(patch.object(ui, 'MaintenanceGuard', InertMaintenanceGuard))
        for method in ('update_dashboard', '_load_metadata', 'refresh_drives', '_load_turbo_states',
                       '_check_updates_thread', '_check_app_update'):
            patches.enter_context(patch.object(ui.PanaceaApp, method, lambda self: None))
        for module, name in ((ui.subprocess, 'Popen'), (ui.subprocess, 'run'),
                             (ui.os, 'startfile'), (ui.webbrowser, 'open'),
                             (ui.messagebox, 'askyesno')):
            patches.enter_context(patch.object(module, name, denied))
        ctk.set_widget_scaling(args.scale)
        ctk.set_window_scaling(1)
        app = ui.PanaceaApp()
        app.geometry(f'{args.width}x{args.height}')
        app.attributes('-topmost', True)
        app.app_update_status.configure(text=LABEL, text_color=ui.COL_WARNING)
        app.btn_check_update.configure(state='disabled')
        app.report_callback_exception = lambda kind, error, traceback: errors.append(str(error))
        closing = False
        def close():
            nonlocal closing
            if closing:
                return
            closing = True
            app._shutdown.set()
            app._resurrect_cancel.set()
            app._update_cancel.set()
            app.workers.close()
            for gate in releases:
                gate.set()
            app.workers.join(2)
            app.monitor.close()
            for callback in app.tk.call('after', 'info'):
                app.tk.call('after', 'cancel', callback)
            app.destroy()
        def prepare():
            try:
                ready, verify = fixture(ui, app, args.case, releases)
                def save_when_ready():
                    try:
                        if not ready():
                            app.after(25, save_when_ready)
                            return
                        observed.update(verify())
                        app.update_idletasks()
                        app.after(250, save)
                    except Exception as exc:
                        errors.append(f'Fixture assertion: {type(exc).__name__}: {exc}')
                        close()
                save_when_ready()
            except Exception as exc:
                errors.append(f'Fixture preparation: {type(exc).__name__}: {exc}')
                close()
        def save():
            try:
                assert app.app_update_status.cget('text') == LABEL
                x, y = app.winfo_rootx(), app.winfo_rooty()
                width, height = app.winfo_width(), app.winfo_height()
                assert width >= 640 and height >= 400
                assert x >= 0 and y >= 0 and x + width <= app.winfo_screenwidth() and y + height <= app.winfo_screenheight()
                path = args.output / f'{args.case}.png'
                ImageGrab.grab(bbox=(x, y, x + width, y + height)).save(path)
                observed.update(pixels=[width, height], screen_pixels=[app.winfo_screenwidth(), app.winfo_screenheight()],
                                image_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                native_window_dpi=ctypes.windll.user32.GetDpiForWindow(app.winfo_id()))
            except Exception as exc:
                errors.append(f'Capture: {type(exc).__name__}: {exc}')
            finally:
                close()
        def timeout():
            errors.append('UI fixture exceeded 12 seconds')
            close()
        app.after(400, prepare)
        app.after(12000, timeout)
        app.mainloop()
    logger.removeHandler(handler)
    record = {'case': args.case, 'section': CASES[args.case][0], 'state': CASES[args.case][1],
              'description': CASES[args.case][2], 'fixture_only': True, 'visible_label': LABEL,
              'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'widget_scale': args.scale,
              'scaling_method': 'CTk widget simulation; window scale 1; no Windows scaling change.',
              'source_sha256': source_hashes(), 'observed': observed, 'callback_errors': errors}
    (args.output / f'{args.case}.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    if errors:
        raise RuntimeError('; '.join(errors))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'docs/validation/screenshots/v2-states')
    parser.add_argument('--width', type=int, default=1366)
    parser.add_argument('--height', type=int, default=768)
    parser.add_argument('--scale', type=float, default=1)
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--list', action='store_true', help='List fixture coverage without opening any GUI')
    args = parser.parse_args()
    if args.list:
        print(json.dumps(CASES, indent=2))
        return
    if sys.platform != 'win32':
        parser.error('Native capture currently requires Windows')
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.case:
        capture(args)
        return
    results = []
    for name in CASES:
        command = [sys.executable, str(Path(__file__).resolve()), '--case', name,
                   '--output', str(args.output), '--width', str(args.width), '--height', str(args.height),
                   '--scale', str(args.scale)]
        child = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=25,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        record = json.loads((args.output / f'{name}.json').read_text(encoding='utf-8')) if (args.output / f'{name}.json').exists() else {}
        results.append({'case': name, 'exit_code': child.returncode, 'record': record,
                        'stdout': child.stdout, 'stderr': child.stderr})
        print(f'{name}: {"PASS" if child.returncode == 0 else "FAIL"}', flush=True)
    manifest = {'fixture_only': True, 'case_count': len(results), 'source_sha256': source_hashes(),
                'all_passed': all(row['exit_code'] == 0 for row in results), 'captures': results}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    if not manifest['all_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

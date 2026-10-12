import threading
from types import SimpleNamespace
from unittest.mock import Mock
import panacea_ui
from panacea_ui import PanaceaApp
from modules.ui_dispatch import UiDispatcher, WorkerController


def app_without_window():
    app = PanaceaApp.__new__(PanaceaApp)
    app.tk = SimpleNamespace()
    app.dispatcher = UiDispatcher()
    app.workers = WorkerController(app.dispatcher)
    app._shutdown = threading.Event()
    app._resurrect_cancel = threading.Event()
    app._update_downloading = False
    app.log_god_msg = Mock()
    app.log_msg = Mock()
    app._resurrection_progress = Mock()
    app.restore_mgr = SimpleNamespace(create_restore_point=Mock(return_value=(True, 'verified new point')))
    app.cleanup_mgr = SimpleNamespace(clean_browser_caches=Mock(return_value=(2, 100)), clean_temp_files=Mock(return_value=(3, 200)), empty_recycle_bin=Mock(return_value=(True, 'emptied')), last_result=None)
    app.cmd_runner = SimpleNamespace(run_command_stream=Mock(return_value=True))
    app.disk_opt = SimpleNamespace(analyze_optimize_drive=Mock(return_value=True))
    return app


def test_restore_failure_stops_before_deleting_any_files():
    app = app_without_window()
    app.restore_mgr.create_restore_point.return_value = (False, 'sequence unavailable')
    result = app._run_resurrection_sequence()
    assert result['status'] == 'failed'
    assert len(result['steps']) == 1
    assert result['steps'][0]['success'] is False
    app.cleanup_mgr.clean_browser_caches.assert_not_called()
    app.cleanup_mgr.empty_recycle_bin.assert_not_called()


def test_failed_command_is_persistent_partial_result_and_progress_follows_completion():
    app = app_without_window()
    app.cmd_runner.run_command_stream.side_effect = [True, False, True, True, True]
    result = app._run_resurrection_sequence()
    assert result['status'] == 'partial'
    assert len(result['steps']) == 10
    assert [row['name'] for row in result['steps'] if not row['success']] == ['Network reset']
    assert app._resurrection_progress.call_count == 0
    app.dispatcher.drain()
    progresses = [call.args[0] for call in app._resurrection_progress.call_args_list]
    assert progresses == [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def test_cancel_between_steps_preserves_completed_results():
    app = app_without_window()
    def restore(description):
        app._resurrect_cancel.set()
        return True, 'verified'
    app.restore_mgr.create_restore_point.side_effect = restore
    result = app._run_resurrection_sequence()
    assert result['status'] == 'cancelled'
    assert len(result['steps']) == 1
    app.cleanup_mgr.clean_browser_caches.assert_not_called()


def test_cleanup_errors_are_not_reported_as_success():
    app = app_without_window()
    def cleanup():
        app.cleanup_mgr.last_result = SimpleNamespace(errors=['locked'], skipped=[], ok=False)
        return 2, 100
    app.cleanup_mgr.clean_browser_caches.side_effect = cleanup
    result = app._run_resurrection_sequence()
    assert result['status'] == 'partial'
    assert result['steps'][1]['success'] is False


def test_turbo_unknown_queries_remain_unknown():
    app = app_without_window()
    app.perf_mgr = SimpleNamespace(get_power_plan=lambda: None, get_visual_effects=lambda: None,
        get_sysmain_status=lambda: False, get_wsearch_status=lambda: True, get_spooler_status=lambda: None,
        is_turbo_active=lambda: None)
    states, master = app._read_turbo_states()
    assert states == {'power': None, 'visual': None, 'sysmain': True, 'wsearch': False, 'spooler': None}
    assert master is None


def test_cancelled_cleanup_confirmation_does_not_start_worker(monkeypatch):
    app = app_without_window()
    app._request_operation = Mock()
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', lambda *args, **kwargs: False)
    app.run_clean_temp()
    app._request_operation.assert_not_called()


def test_non_frozen_update_opens_release_page_without_installing(monkeypatch):
    app = app_without_window()
    app._release = SimpleNamespace(release_url='https://github.com/falker47/Panacea/releases/tag/v1.49.0')
    app._request_operation = Mock()
    opened = []
    monkeypatch.setattr(panacea_ui.sys, 'frozen', False, raising=False)
    monkeypatch.setattr(panacea_ui.webbrowser, 'open', opened.append)
    app._auto_update()
    assert opened == ['https://github.com/falker47/Panacea/releases/tag/v1.49.0']
    app._request_operation.assert_not_called()

def test_maintenance_cannot_start_during_update_download():
    app = app_without_window()
    app._update_installing = False
    app._update_downloading = True
    app._show_toast = Mock()
    app.operation_label = Mock()
    app._set_maintenance_state = Mock()
    entered, release = threading.Event(), threading.Event()
    def download():
        entered.set(); release.wait(2)
    app.workers.start('download', download, group='app-update')
    assert entered.wait(2)
    work = Mock()
    assert app._request_operation('cleanup', work) is False
    release.set(); app.workers.join(2); app.dispatcher.drain()
    work.assert_not_called()


def test_duplicate_resurrection_does_not_clear_pending_cancellation(monkeypatch):
    app = app_without_window()
    app._resurrect_cancel.set()
    app._update_installing = False
    app._show_toast = Mock()
    app._request_operation = Mock(return_value=False)
    monkeypatch.setattr(app.workers, 'busy', lambda group='maintenance': True)
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', lambda *args, **kwargs: True)
    app.run_god_mode()
    assert app._resurrect_cancel.is_set()


def test_preview_reports_incomplete_inspection_as_partial():
    app = app_without_window()
    app.preview_label = Mock()
    app.operation_label = Mock()
    app.select_frame = Mock()
    app.cleanup_mgr.preview_temp_files = lambda: (0, 0)
    app.cleanup_mgr.last_result = SimpleNamespace(errors=['invalid root'], skipped=[], ok=False)
    app._request_operation = lambda name, work, show: show(work())
    app.run_preview_temp()
    status = app.operation_label.configure.call_args.kwargs['text']
    assert 'partial' in status.lower() or 'failed' in status.lower()

def test_centering_preserves_requested_geometry_when_it_fits():
    assert PanaceaApp._fit_window_size(1100, 700, 1920, 1080, 1.0) == (1100, 700)


def test_centering_clamps_large_geometry_to_scaled_work_area():
    assert PanaceaApp._fit_window_size(1100, 700, 1366, 728, 1.5) == (878, 453)


def test_battery_report_uses_system_directory_and_single_output_path(monkeypatch):
    app = app_without_window()
    calls = []
    app._request_operation = lambda name, work, done: work()
    monkeypatch.setenv('USERPROFILE', r'C:\Users\A Name')
    monkeypatch.setattr(panacea_ui.subprocess, 'run', lambda args, **kwargs: calls.append((args, kwargs)))
    import modules.commands
    monkeypatch.setattr(modules.commands, 'system_executable', lambda name: 'C:\\Windows\\System32\\' + name)
    app.run_battery_report()
    assert calls[0][0] == [r'C:\Windows\System32\powercfg.exe', '/batteryreport', '/output', r'C:\Users\A Name\battery_report.html']
    assert calls[0][1]['shell'] is False

def test_navigation_builds_each_section_only_when_first_opened():
    app = app_without_window()
    app.frames = {'Dashboard': Mock(), 'Disk': Mock()}
    app.nav_buttons = {'Dashboard': Mock(), 'Disk': Mock()}
    dashboard, disk = Mock(), Mock()
    app._setup_functions = {'Dashboard': dashboard, 'Disk': disk}
    app._built_frames = set()
    app.select_frame('Dashboard')
    app.select_frame('Dashboard')
    assert dashboard.call_count == 1
    disk.assert_not_called()
    app.select_frame('Disk')
    assert disk.call_count == 1
    assert app.active_frame == 'Disk'


def test_actual_turbo_state_is_cached_before_section_is_built():
    app = app_without_window()
    app._turbo_states = {}
    states = {'power': True, 'visual': None, 'sysmain': False, 'wsearch': True, 'spooler': False}
    app._apply_turbo_states((states, None))
    assert app._turbo_states == states
    assert app._turbo_master is None

def test_background_release_check_does_not_block_maintenance():
    app = app_without_window()
    app._update_installing = False
    app._show_toast = Mock()
    app.operation_label = Mock()
    app._set_maintenance_state = Mock()
    release = threading.Event()
    app.workers.start('check', lambda: release.wait(2), group='app-update')
    assert app._request_operation('preview', lambda: None) is True
    release.set(); app.workers.join(2); app.dispatcher.drain()

def _safe_real_app(monkeypatch):
    """Real Tk layout, with every system/network boundary replaced before init."""
    for name in ('Logger', 'CleanupManager', 'DiskOptimizer', 'CommandRunner', 'SystemMonitor', 'RestoreManager', 'PerformanceManager'):
        monkeypatch.setattr(panacea_ui, name, lambda: SimpleNamespace())
    for name in ('update_dashboard', '_load_metadata', 'refresh_drives', '_load_turbo_states', '_check_updates_thread', '_check_app_update'):
        monkeypatch.setattr(PanaceaApp, name, lambda self: None)
    return PanaceaApp()


def _destroy_real_app(app):
    app._shutdown.set()
    app.workers.close()
    for callback_id in app.tk.call('after', 'info'):
        app.after_cancel(callback_id)
    app.destroy()


def test_real_tk_first_mapping_retains_a_usable_requested_size(monkeypatch):
    import pytest
    import sys
    if sys.platform != 'win32' and not panacea_ui.os.environ.get('DISPLAY'):
        pytest.skip('Real Tk mapping requires a display')
    app = _safe_real_app(monkeypatch)
    try:
        app.geometry('1100x700')
        app.update()
        scale = app._get_window_scaling()
        assert app.winfo_ismapped()
        assert app.winfo_width() / scale >= 760
        assert app.winfo_height() / scale >= 420
        if app.winfo_screenwidth() >= 1100 * scale + 48 and app.winfo_screenheight() >= 700 * scale + 120:
            assert abs(app.winfo_width() / scale - 1100) < 2
            assert abs(app.winfo_height() / scale - 700) < 2
    finally:
        _destroy_real_app(app)


def test_real_tk_user_resize_after_mapping_respects_minimum(monkeypatch):
    import pytest
    import sys
    if sys.platform != 'win32' and not panacea_ui.os.environ.get('DISPLAY'):
        pytest.skip('Real Tk mapping requires a display')
    app = _safe_real_app(monkeypatch)
    try:
        app.update()
        app.geometry('900x600')
        app.update()
        scale = app._get_window_scaling()
        assert abs(app.winfo_width() / scale - 900) < 2
        assert abs(app.winfo_height() / scale - 600) < 2
        app.geometry('200x200')
        app.update()
        assert app.winfo_width() / scale >= 760
        assert app.winfo_height() / scale >= 420
    finally:
        _destroy_real_app(app)

import pytest


@pytest.mark.parametrize('width,height,scale', [(1366, 768, 1.5), (1020, 680, 1.0)])
def test_real_tk_dashboard_primary_metrics_and_actions_fit_initial_viewport(monkeypatch, width, height, scale):
    if panacea_ui.sys.platform != 'win32' and not panacea_ui.os.environ.get('DISPLAY'):
        pytest.skip('Real Tk layout requires a display')
    panacea_ui.ctk.set_widget_scaling(scale)
    panacea_ui.ctk.set_window_scaling(scale)
    app = _safe_real_app(monkeypatch)
    try:
        app.update()
        # Reproduce the hosted runner's small default window-manager limit.
        panacea_ui.tk.Tk.maxsize(app, 1028, 780)
        # Test physical display pixels, independent of CTk logical coordinates.
        # Permit this virtual viewport even when the runner monitor is1024px.
        # Actual visible pixels/DPI are verified separately by screenshot QA.
        panacea_ui.tk.Tk.maxsize(app, width, height)
        panacea_ui.tk.Tk.geometry(app, f'{width}x{height}')
        app._update_fast_gui({'ram': (16, 8, 50), 'disk': (512, 128, 75), 'cpu': 28.5,
                              'uptime': '4d 7h 49m', 'battery': (None, 'Unknown')})
        app._update_metadata_gui({'os': 'Windows 11',
            'cpu_name': 'Intel Core i7-11700 @ 2.50GHz\n(16 logical processors @ 2.5 GHz)',
            'ram_info': 'DDR4 @ 3200 MHz (2 modules)', 'disk_model': 'SSD Samsung NVMe system drive'})
        app.update()
        assert app.winfo_width() == width
        assert app.winfo_height() == height
        viewport = app.frame_dashboard
        left, top = viewport.winfo_rootx(), viewport.winfo_rooty()
        right, bottom = left + viewport.winfo_width(), top + viewport.winfo_height()
        def buttons_in(widget):
            result = []
            for child in widget.winfo_children():
                if isinstance(child, panacea_ui.ctk.CTkButton):
                    result.append(child)
                else:
                    result.extend(buttons_in(child))
            return result
        actions = buttons_in(app.card_sys)
        assert len(actions) == 3
        for widget in [app.dash_cpu_val, app.dash_ram_perc, app.dash_disk_perc, *actions]:
            assert widget.winfo_rooty() >= top
            assert widget.winfo_rooty() + widget.winfo_height() <= bottom, f'{widget.cget("text")} below viewport'
            assert widget.winfo_rootx() >= left
            assert widget.winfo_rootx() + widget.winfo_width() <= right, f'{widget.cget("text")} outside horizontal viewport'
        assert app.card_sys.winfo_rooty() + app.card_sys.winfo_height() <= bottom
    finally:
        _destroy_real_app(app)
        panacea_ui.ctk.set_widget_scaling(1.0)
        panacea_ui.ctk.set_window_scaling(1.0)

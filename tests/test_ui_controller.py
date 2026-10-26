import threading
from types import SimpleNamespace
from unittest.mock import Mock
from functools import wraps
import os
import subprocess
import sys
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
    app.cleanup_mgr.preview_temp_files = lambda **kwargs: (0, 0)
    app.cleanup_mgr.last_result = SimpleNamespace(errors=['invalid root'], skipped=[], ok=False)
    app._request_operation = lambda name, work, show, **kwargs: show(work()) or True
    app.run_preview_temp()
    status = app.operation_label.configure.call_args.kwargs['text']
    assert 'partial' in status.lower() or 'failed' in status.lower()

def test_analysis_results_update_the_dashboard_summary():
    app = app_without_window()
    app.operation_label = Mock()
    app.dash_preview_status = Mock()
    app.select_frame = Mock()
    app.cleanup_mgr.preview_temp_files = lambda **kwargs: (12, 1572864)
    app.cleanup_mgr.last_result = SimpleNamespace(errors=[], skipped=[], ok=True)
    app._request_operation = lambda name, work, show, **kwargs: show(work()) or True
    app.run_preview_temp()
    assert '12 candidates' in app.dash_preview_status.configure.call_args.kwargs['text']
    assert '1.5 MB' in app.dash_preview_status.configure.call_args.kwargs['text']


def test_centering_preserves_requested_geometry_when_it_fits():
    assert PanaceaApp._fit_window_size(1100, 700, 1920, 1080, 1.0) == (1100, 700)


def test_centering_clamps_large_geometry_to_scaled_work_area():
    assert PanaceaApp._fit_window_size(1100, 700, 1366, 728, 1.5) == (878, 453)


def test_battery_report_uses_system_directory_and_single_output_path(monkeypatch):
    app = app_without_window()
    calls = []
    app._request_operation = lambda name, work, done, **kwargs: work()
    monkeypatch.setenv('USERPROFILE', r'C:\Users\A Name')
    monkeypatch.setattr(panacea_ui.subprocess, 'run', lambda args, **kwargs: calls.append((args, kwargs)))
    import modules.commands
    monkeypatch.setattr(modules.commands, 'system_executable', lambda name: 'C:\\Windows\\System32\\' + name)
    app.run_battery_report()
    assert calls[0][0] == [r'C:\Windows\System32\powercfg.exe', '/batteryreport', '/output', r'C:\Users\A Name\battery_report.html']
    assert calls[0][1]['shell'] is False
    assert calls[0][1]['stdin'] == panacea_ui.subprocess.DEVNULL

def test_navigation_builds_each_section_only_when_first_opened():
    app = app_without_window()
    pages = [page for _, _, _, group_pages in app.NAV_GROUPS for page in group_pages]
    app.frames = {page: Mock() for page in pages}
    app.group_frames = {root: Mock() for root, _, _, _ in app.NAV_GROUPS}
    app.nav_buttons = {root: Mock() for root, _, _, _ in app.NAV_GROUPS}
    app.icons = {}
    app.icons_active = {}
    app._setup_functions = {page: Mock() for page in pages}
    app._built_frames = set()
    app.select_frame('Dashboard')
    app.select_frame('Dashboard')
    assert app._setup_functions['Dashboard'].call_count == 1
    app._setup_functions['Disk'].assert_not_called()
    app.select_frame('Disk')
    assert app._setup_functions['Disk'].call_count == 1
    assert app._setup_functions['Tools'].call_count == 1
    assert app.active_frame == 'Disk'
    assert app.group_frames['Tools'].grid.called


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
    monkeypatch.setattr(panacea_ui, 'MaintenanceGuard', lambda: SimpleNamespace(is_blocked=lambda: False, mark_unknown=lambda: True, last_error=''))
    for name in ('Logger', 'CleanupManager', 'DiskOptimizer', 'CommandRunner', 'SystemMonitor', 'RestoreManager', 'PerformanceManager'):
        monkeypatch.setattr(panacea_ui, name, lambda: SimpleNamespace())
    for name in ('update_dashboard', '_load_metadata', 'refresh_drives', '_load_turbo_states', '_check_updates_thread', '_check_app_update'):
        monkeypatch.setattr(PanaceaApp, name, lambda self: None)
    return PanaceaApp()


def _destroy_real_app(app):
    app._shutdown.set()
    app.workers.close()
    for callback_id in app.tk.call('after', 'info'):
        # Cancel scheduling without deleting another widget's registered Tcl
        # command. Its owning widget releases that command during destroy().
        app.tk.call('after', 'cancel', callback_id)
    app.destroy()


def isolated_tk_test(test):
    """Each native layout case owns one fresh Tcl/CTk process, like the app."""
    @wraps(test)
    def run(*args, **kwargs):
        if sys.platform != 'win32' and not os.environ.get('DISPLAY'):
            pytest.skip('Native Tk requires a display')
        if os.environ.get('PANACEA_ISOLATED_TK_CASE') == test.__name__:
            return test(*args, **kwargs)
        node = 'tests/test_ui_controller.py::' + test.__name__
        if 'width' in kwargs:
            node += f"[{kwargs['width']}-{kwargs['height']}-{kwargs['scale']}]"
        environment = os.environ.copy()
        environment['PANACEA_ISOLATED_TK_CASE'] = test.__name__
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-s', node],
            env=environment, stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        assert result.returncode == 0, result.stdout + result.stderr
        assert '1 passed' in result.stdout, 'The child must execute exactly one native case: ' + result.stdout
    return run


@isolated_tk_test
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


@isolated_tk_test
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


def _native_widgets(parent, kind):
    for child in parent.winfo_children():
        if isinstance(child, kind):
            yield child
        yield from _native_widgets(child, kind)


def _native_bounds(widget):
    return (widget.winfo_rootx(), widget.winfo_rooty(),
            widget.winfo_rootx() + widget.winfo_width(),
            widget.winfo_rooty() + widget.winfo_height())


@pytest.mark.parametrize('width,height,scale', [
    (1366, 768, 1.0), (1366, 768, 1.25), (1366, 768, 1.5),
    (1920, 1080, 1.0), (1920, 1080, 1.25), (1920, 1080, 1.5),
])
@isolated_tk_test
def test_real_tk_polish_geometry_survives_viewport_resize(monkeypatch, width, height, scale):
    panacea_ui.ctk.set_widget_scaling(scale)
    panacea_ui.ctk.set_window_scaling(1)
    app = _safe_real_app(monkeypatch)
    problems = []

    def expect(condition, message):
        if not condition:
            problems.append(message)

    def font_metric(rendered, metric):
        # Font(font=...) recreates the font through `font actual`, which can
        # round pixel sizes to points. Query the exact rendered description.
        return int(rendered.tk.call('font', 'metrics', rendered.cget('font'),
                                    '-displayof', rendered, '-' + metric))

    def baseline(label):
        rendered = label._label
        return (rendered.winfo_rooty() + (rendered.winfo_height() - font_metric(rendered, 'linespace')) / 2
                + font_metric(rendered, 'ascent'))

    def inside(widget, container, name):
        left, top, right, bottom = _native_bounds(widget)
        bounds = _native_bounds(container)
        expect(bounds[0] - 2 <= left < right <= bounds[2] + 2
               and bounds[1] - 2 <= top < bottom <= bounds[3] + 2, f'{name} clipped: {(left, top, right, bottom)} vs {bounds}')

    try:
        app.update()
        footer_insets = []
        for window_width, window_height in ((width, height), (width - 160, height - 96), (width, height)):
            panacea_ui.tk.Tk.maxsize(app, width, height)
            panacea_ui.tk.Tk.geometry(app, f'{window_width}x{window_height}')
            app.select_frame('Dashboard')
            app.update()
            dashboard_canvas = app.card_sys.master._parent_canvas
            dashboard_canvas.yview_moveto(0)
            app.update()
            labels = list(_native_widgets(app.sidebar_frame, panacea_ui.ctk.CTkLabel))
            version, credit = app.footer_version, app.footer_credit
            expect(version.cget('text') == f'v{panacea_ui.VERSION}',
                   'Footer must show current version')
            expect(credit.cget('text') == 'Panacea 2026 — Maurizio Falconi (falker47)',
                   'Footer credit must contain the full attribution')
            expect(_native_bounds(credit)[3] <= _native_bounds(version)[1] + 2,
                   'Footer version should sit below the linked credit')
            expect(_native_bounds(app.update_bar)[3] <= _native_bounds(credit)[1],
                   'Update status must precede attribution')
            expect(not app.btn_check_update.winfo_manager(),
                   'Do not show an update button while checking')
            sidebar = _native_bounds(app.sidebar_frame)
            footer_bottom = _native_bounds(version)[3]
            insets = (_native_bounds(credit)[0] - sidebar[0],
                      sidebar[2] - _native_bounds(version)[2],
                      sidebar[3] - footer_bottom)
            footer_insets.append(insets)
            expect(all(0 <= inset <= 22 * scale for inset in insets),
                   f'Footer edge insets too large: {insets}')
            for label in (version, credit, app.app_update_status):
                inside(label, app.sidebar_frame, 'Footer')
            title = next(label for label in labels if label.cget('text') == 'Panacea')
            tagline = next(label for label in labels if label.cget('text') == 'SYSTEM MAINTENANCE')
            gap = tagline._label.winfo_rooty() - (title._label.winfo_rooty() + title._label.winfo_height())
            expect(-1 <= gap <= 0.6 * tagline._label.winfo_height() + 2, f'Brand text gap is not compact: {gap}')
            expect(all(icon.cget('size') == (35, 35) for icon in app.icons.values()), 'Sidebar navigation icons must be 35px')
            expect(app.brand_icon.cget('size') == (74, 74), 'Original brand logo should render at 74px')
            for branding in (app.brand_title, app.brand_tagline):
                inside(branding, app.sidebar_frame, 'Sidebar branding')
                rendered = branding._label
                required = int(rendered.tk.call('font', 'measure', rendered.cget('font'),
                                                '-displayof', rendered, branding.cget('text')))
                expect(required <= rendered.winfo_width() + 2,
                       f'Branding text clips: {branding.cget("text")}')
            expect(app.brand_title.cget('font').cget('size') == 32, 'Panacea title is undersized')
            expect(app.brand_tagline.cget('font').cget('size') == 12, 'System maintenance subtitle is undersized')
            expect(_native_bounds(app.nav_buttons['Dashboard'])[1] -
                   _native_bounds(app._sidebar_brand)[3] >= 5 * scale,
                   'The navigation needs breathing room below branding')
            for root, label, _, _ in app.NAV_GROUPS:
                button = app.nav_buttons[root]
                expect(button.cget('text') == label, f'{root} navigation label changed')
                expect(button.cget('font').cget('size') == 16, f'{root} navigation font is undersized')
                expect(button.cget('font').cget('family') == 'Segoe UI Semibold',
                       f'{root} navigation font should be semibold')
                inside(button, app.sidebar_frame, root + ' navigation')
                rendered = button._text_label
                required = int(rendered.tk.call('font', 'measure', rendered.cget('font'),
                                                '-displayof', rendered, label))
                expect(required <= rendered.winfo_width() + 2,
                       f'{root} navigation text clips: {required}px > {rendered.winfo_width()}px')
            for name in ('cpu', 'memory', 'drive'):
                expect(app.action_icons[name].cget('size') == (22, 22), f'{name} metric icon was resized')
            dashboard_labels = list(_native_widgets(app.frame_dashboard, panacea_ui.ctk.CTkLabel))
            for name in ('scan', 'restore', 'updates'):
                icon = next(label for label in dashboard_labels if label.cget('image') is app.action_icons[name])
                image_height = int(app.tk.call('image', 'height', icon._label.cget('image')))
                text_labels = [label for label in _native_widgets(icon.master, panacea_ui.ctk.CTkLabel) if label.cget('text')]
                text_top = min(label._label.winfo_rooty() for label in text_labels)
                text_bottom = max(label._label.winfo_rooty() + label._label.winfo_height() for label in text_labels)
                expect(image_height >= 0.65 * (text_bottom - text_top), f'{name} image too small for its text group')
                stacked = sorted(text_labels, key=lambda label: label._label.winfo_rooty())
                for upper, lower in zip(stacked, stacked[1:]):
                    text_gap = lower._label.winfo_rooty() - _native_bounds(upper._label)[3]
                    line_height = font_metric(lower._label, 'linespace')
                    expect(-1 <= text_gap <= line_height * 0.65 + 2,
                           f'{name} title/detail gap is not compact or overlaps: {text_gap}')
                inside(icon, icon.master, name + ' icon')
                for label in text_labels:
                    inside(label, icon.master, name + ' text')
                    expect(_native_bounds(icon)[2] <= _native_bounds(label)[0] + 2, name + ' icon overlaps text')
                for button in _native_widgets(icon.master, panacea_ui.ctk.CTkButton):
                    inside(button, icon.master, name + ' action')
                    expect(max(_native_bounds(label)[2] for label in text_labels) <= _native_bounds(button)[0] + 2,
                           name + ' text overlaps its action')
            if window_height < height:
                # Smaller than the requested display matrix: actions may scroll,
                # but must remain reachable without disturbing the fixed footer.
                dashboard_canvas.yview_moveto(1)
                app.update()
            inside(app.card_sys, app.frame_dashboard, 'Dashboard action cards')
            app.select_frame('Cleaning')
            app.update()
            # Quick cleanup is the first visible action; individual tools stay
            # available on demand without crowding the initial viewport.
            quick = app.quick_cleanup_card
            expect(not app.cleanup_individuals_frame.winfo_manager(),
                   'Individual cleanup tools must start collapsed')
            inside(app.quick_cleanup_button, quick, 'Quick cleanup action')
            expect(bool(quick.winfo_ismapped()), 'Quick cleanup card must be available')
            expect(_native_bounds(app.frame_cleaning)[0] <= _native_bounds(quick)[0]
                   and _native_bounds(quick)[2] <= _native_bounds(app.frame_cleaning)[2],
                   'Quick cleanup card must fit the panel width')
            app._toggle_cleanup_tools()
            app.update()
            expect(bool(app.cleanup_individuals_frame.winfo_manager()),
                   'Individual cleanup tools should expand')
            expect(not hasattr(app, 'preview_label') and not hasattr(app, 'cleanup_reasons_button'),
                   'Individual tools must not create the duplicate analysis card')
            visible_titles = [label.cget('text') for label in
                              _native_widgets(app.cleanup_individuals_frame, panacea_ui.ctk.CTkLabel)
                              if label.cget('text')]
            expected = ('Delete temporary files', 'Recycle Bin', 'Component store',
                        'Windows Disk Cleanup')
            expect([title for title in visible_titles if title in expected] == list(expected),
                   'Expanded cleanup tools must show exactly the four manual operations')
            buttons = [button.cget('text') for button in
                       _native_widgets(app.cleanup_individuals_frame, panacea_ui.ctk.CTkButton)]
            expect(buttons == ['Clean now', 'Empty bin', 'Clean store', 'Open utility'],
                   f'Unexpected individual cleanup actions: {buttons}')
            expect(not any(label.cget('image') for label in
                           _native_widgets(quick, panacea_ui.ctk.CTkLabel)),
                   'Quick cleanup must remain icon-free')
            app._toggle_cleanup_tools()
            app.update()
            app.select_frame('Resurrect')
            app.update()
            resurrection_canvas = app.god_log.master.master._parent_canvas
            resurrection_canvas.yview_moveto(0)
            app.update()
            for widget, label in ((app.btn_resurrect_start, 'Start sequence'),
                                  (app.lbl_status, 'Resurrection status'),
                                  (app.progress_bar, 'Resurrection progress')):
                inside(widget, resurrection_canvas, label)
            status_bounds = _native_bounds(app.lbl_status)
            start_bounds = _native_bounds(app.btn_resurrect_start)
            expect(status_bounds[2] <= start_bounds[0] or start_bounds[2] <= status_bounds[0]
                   or status_bounds[3] <= start_bounds[1] or start_bounds[3] <= status_bounds[1],
                   'Resurrection status overlaps Start sequence')
            expect(len(app._resurrection_rows) == len(app.RESURRECTION_STEPS) == 10,
                   'Every Resurrection phase must have a visible status')
            for name, status in app._resurrection_rows.items():
                phase = status.master
                phase_labels = [label for label in _native_widgets(phase, panacea_ui.ctk.CTkLabel)
                                if label.winfo_ismapped()]
                for label in phase_labels:
                    inside(label, phase, f'{name} phase text')
                    rendered = label._label
                    text_width = int(rendered.tk.call('font', 'measure', rendered.cget('font'),
                                                      '-displayof', rendered, label.cget('text')))
                    line_height = font_metric(rendered, 'linespace')
                    expect(text_width <= rendered.winfo_width() + 2,
                           f'{name} phase text is horizontally clipped: {label.cget("text")}; '
                           f'required={text_width}px, available={rendered.winfo_width()}px')
                    expect(line_height <= rendered.winfo_height() + 2,
                           f'{name} phase text is vertically clipped: '
                           f'required={line_height}px, available={rendered.winfo_height()}px')
                ordered = sorted(phase_labels, key=lambda label: label.winfo_rootx())
                for previous, following in zip(ordered, ordered[1:]):
                    expect(_native_bounds(previous)[2] <= _native_bounds(following)[0] + 2,
                           f'{name} phase labels overlap')
                if window_height == height:
                    inside(phase, resurrection_canvas, name + ' phase')
            if window_height < height:
                resurrection_canvas.yview_moveto(1)
                app.update()
                for name in (app.RESURRECTION_STEPS[4], app.RESURRECTION_STEPS[-1]):
                    inside(app._resurrection_rows[name].master, resurrection_canvas, name + ' phase after scroll')
            output_panel = app.god_log.master
            output_toggle = next(button for button in output_panel.winfo_children()
                                 if isinstance(button, panacea_ui.ctk.CTkButton))
            inside(output_panel, resurrection_canvas, 'Full sequence panel')
            inside(output_toggle, resurrection_canvas, 'Full sequence output toggle')
        expect(all(abs(pair[axis] - footer_insets[0][axis]) <= 4 for pair in footer_insets for axis in (0, 1, 2)),
               f'Footer insets drift on resize: {footer_insets}')
        assert not problems, '\n'.join(problems)
    finally:
        _destroy_real_app(app)
        panacea_ui.ctk.set_widget_scaling(1.0)
        panacea_ui.ctk.set_window_scaling(1.0)


@pytest.mark.parametrize('width,height,scale', [(1366, 768, 1.5), (1020, 680, 1.0)])
@isolated_tk_test
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
        assert len(actions) == 2  # Analyze and restore; sidebar already opens Cleanup.
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


def test_application_close_cancels_monitor_queries_before_destroying_tk():
    app = app_without_window()
    app._update_installing = False
    app._update_cancel = threading.Event()
    calls = []
    app.monitor = SimpleNamespace(close=lambda: calls.append('monitor-close'))
    app.destroy = lambda: calls.append('destroy')
    app._on_close()
    assert calls == ['monitor-close', 'destroy']
    assert app._shutdown.is_set()
    assert app._update_cancel.is_set()


def test_update_replacement_guard_keeps_monitor_running_when_close_is_refused():
    app = app_without_window()
    app._update_installing = True
    app._show_toast = Mock()
    app.monitor = SimpleNamespace(close=Mock())
    app.destroy = Mock()
    app._on_close()
    app.monitor.close.assert_not_called()
    app.destroy.assert_not_called()
    assert not app._shutdown.is_set()


@pytest.mark.parametrize('method,manager,backend', [
    ('run_cleanmgr', 'cleanup_mgr', 'open_disk_cleanup'),
    ('run_dfrgui', 'disk_opt', 'open_optimize_gui'),
])
def test_failed_windows_tool_launch_has_visible_error(method, manager, backend):
    app = app_without_window()
    setattr(app, manager, SimpleNamespace(**{backend: lambda: False}))
    app._show_toast = Mock()
    app.operation_label = Mock()
    getattr(app, method)()
    assert app._show_toast.call_args.args[2] == 'error'


def test_resurrection_targets_windows_system_drive(monkeypatch):
    app = app_without_window()
    monkeypatch.setenv('SystemDrive', 'D:')
    monkeypatch.setattr('modules.commands.system_executable', lambda name: 'D:\\Windows\\System32\\' + name)
    app._run_resurrection_sequence()
    assert app.disk_opt.analyze_optimize_drive.call_args.args[0] == 'D:'
    commands = [call.args[0] for call in app.cmd_runner.run_command_stream.call_args_list]
    assert 'chkdsk D: /scan /perf' in commands


def test_completed_resurrection_step_updates_only_its_actual_result():
    app = app_without_window()
    app._resurrection_states = {}
    app._resurrection_rows = {}
    app._set_resurrection_step('Restore point', 'completed', 'Verified checkpoint')
    app._set_resurrection_step('Browser caches', 'failed', 'One locked file')
    assert app._resurrection_states == {
        'Restore point': ('completed', 'Verified checkpoint'),
        'Browser caches': ('failed', 'One locked file'),
    }


def test_cancelled_resurrection_marks_unattempted_steps_without_success():
    app = app_without_window()
    app._resurrection_states = {'Restore point': ('completed', 'Verified')}
    app._resurrection_rows = {}
    app.lbl_status = Mock()
    app.operation_label = Mock()
    result = {'status': 'cancelled', 'steps': [
        {'name': 'Restore point', 'success': True, 'message': 'Verified'}], 'total': 10}
    app._finish_resurrection(result)
    assert app._resurrection_states['Restore point'][0] == 'completed'
    assert app._resurrection_states['Browser caches'][0] == 'not run'
    assert app.last_resurrection_result == result


def test_restore_saved_turbo_is_available_after_partial_activation():
    app = app_without_window()
    app.btn_restore_turbo = Mock()
    app.turbo_saved_label = Mock()
    app._update_installing = False
    app._apply_saved_turbo(('power',))
    assert app.btn_restore_turbo.configure.call_args.kwargs['state'] == 'normal'
    assert '1' in app.turbo_saved_label.configure.call_args.kwargs['text']


def test_no_drives_disables_optimization_without_selecting_fake_drive():
    app = app_without_window()
    app.drive_menu = Mock()
    app.selected_drive = Mock(get=lambda: 'C:')
    app.btn_optimize_drive = Mock()
    app.drive_detail = Mock()
    app._update_installing = False
    app._set_drives([])
    assert app.selected_drive.set.call_args.args == ('No drives',)
    assert app.btn_optimize_drive.configure.call_args.kwargs['state'] == 'disabled'


@pytest.mark.parametrize('width,height,scale', [(1366, 768, 1.5)])
@isolated_tk_test
def test_real_tk_all_section_actions_and_phases_fit_initial_viewport(monkeypatch, width, height, scale):
    panacea_ui.ctk.set_widget_scaling(scale)
    panacea_ui.ctk.set_window_scaling(1)
    app = _safe_real_app(monkeypatch)
    try:
        app.update()
        panacea_ui.tk.Tk.maxsize(app, width, height)
        panacea_ui.tk.Tk.geometry(app, f'{width}x{height}')
        def actions(widget):
            found = []
            for child in widget.winfo_children():
                if isinstance(child, (panacea_ui.ctk.CTkButton, panacea_ui.ctk.CTkSwitch)):
                    if child.winfo_ismapped():
                        found.append(child)
                else:
                    found.extend(actions(child))
            return found
        for name in ('Cleaning', 'Apps', 'Tools', 'Disk', 'Turbo', 'Startup', 'Resurrect'):
            app.select_frame(name)
            app.update()
            frame = app.frames[name]
            left, top = frame.winfo_rootx(), frame.winfo_rooty()
            right, bottom = left + frame.winfo_width(), top + frame.winfo_height()
            widgets = actions(frame)
            if name == 'Resurrect':
                widgets += list(app._resurrection_rows.values())
            for widget in widgets:
                assert widget.winfo_rootx() >= left
                assert widget.winfo_rootx() + widget.winfo_width() <= right, (
                    f'{name}: {widget.cget("text")} outside viewport horizontally')
                if widget.winfo_rooty() + widget.winfo_height() > bottom:
                    # The combined columns are independently scrollable; their
                    # lower controls must remain reachable, not always on screen.
                    parent = widget.master
                    while parent is not None and not isinstance(parent, panacea_ui.ctk.CTkScrollableFrame):
                        parent = getattr(parent, 'master', None)
                    assert parent is not None, f'{name}: {widget.cget("text")} not scrollable'
                    assert parent._parent_canvas.yview()[1] < 1.0, (
                        f'{name}: {widget.cget("text")} clipped without scroll')
                else:
                    assert widget.winfo_rooty() >= top
            if name == 'Cleaning':
                log = app.clean_log
                toggle = next(child for child in log.master.winfo_children()
                              if isinstance(child, panacea_ui.ctk.CTkButton))
                assert not log.winfo_manager()
                toggle.invoke()
                app.update()
                assert log.winfo_ismapped()
                canvas = app.group_scroll['Cleaning']._parent_canvas
                before = canvas.yview()
                assert before[1] < 1.0, 'Expanded details should overflow the compact viewport'
                canvas.event_generate('<MouseWheel>', delta=-120)
                app.update()
                assert canvas.yview()[0] > before[0]
                toggle.invoke()
                app.update()
                assert not log.winfo_manager()
    finally:
        _destroy_real_app(app)


def test_unavailable_metrics_do_not_render_zero_or_healthy():
    app = app_without_window()
    names = ('dash_uptime_val', 'dash_cpu_val', 'cpu_graph', 'ram_graph', 'dash_ram_val', 'dash_ram_perc',
             'dash_disk_bar', 'dash_disk_state', 'dash_disk_val', 'dash_disk_perc', 'dash_battery')
    for name in names:
        setattr(app, name, Mock())
    app._update_fast_gui({'ram': None, 'disk': None, 'cpu': None, 'uptime': 'Unknown', 'battery': (None, 'Unknown')})
    assert app.dash_cpu_val.configure.call_args.kwargs['text'] == '—'
    assert app.dash_disk_state.configure.call_args.kwargs['text'] == 'Unavailable'
    app.cpu_graph.add_value.assert_not_called()
    app.ram_graph.add_value.assert_not_called()


def test_battery_report_open_failure_preserves_saved_result(monkeypatch, tmp_path):
    app = app_without_window()
    app.operation_label = Mock()
    app._show_toast = Mock()
    monkeypatch.setattr(panacea_ui.os, 'startfile', Mock(side_effect=OSError('No HTML association')), raising=False)
    app._request_operation = lambda name, work, success, **kwargs: success(tmp_path / 'battery_report.html')
    app.run_battery_report()
    text = app.operation_label.configure.call_args.kwargs['text']
    assert 'saved' in text.lower() and 'battery_report.html' in text
    assert app._show_toast.call_args.args[2] == 'warning'


def test_callback_drain_does_not_reschedule_after_queued_shutdown():
    app = app_without_window()
    app.after = Mock()
    app.dispatcher.post(app._shutdown.set)
    app._drain_callbacks()
    app.after.assert_not_called()


def test_close_defers_until_owned_maintenance_finishes(monkeypatch):
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', lambda *args, **kwargs: True)
    app = app_without_window()
    app._update_installing = False
    app._update_cancel = threading.Event()
    app._maintenance_controls = []
    app.operation_label = Mock()
    app._show_toast = Mock()
    app.monitor = SimpleNamespace(close=Mock())
    app.destroy = Mock()
    entered, release = threading.Event(), threading.Event()
    def maintenance():
        entered.set()
        release.wait(3)
        return True
    try:
        assert app._request_operation('fixture', maintenance)
        assert entered.wait(3)
        app._on_close()
        app.destroy.assert_not_called()
        assert app._resurrect_cancel.is_set()
        release.set()
        app.workers.join(3)
        app.dispatcher.drain()
        app.destroy.assert_called_once()
        app.monitor.close.assert_called_once()
    finally:
        release.set()
        app.workers.join(3)


@pytest.mark.parametrize('target', ['ms-settings:appsfeatures', 'ms-settings:startupapps',
                                   'ms-settings:windowsupdate', 'ms-settings:windowsupdate-optionalupdates'])
def test_windows_settings_routes_exact_destination_without_claiming_completion(monkeypatch, target):
    app = app_without_window()
    app.operation_label = Mock()
    app.apps_status = Mock()
    opened = []
    monkeypatch.setattr(panacea_ui.os, 'startfile', opened.append, raising=False)
    app.run_launch(target, 'Windows settings')
    assert opened == [target]
    assert app.operation_label.configure.call_args.kwargs['text'].startswith('Opened')


def test_windows_settings_failure_replaces_previous_success(monkeypatch):
    app = app_without_window()
    app.operation_label = Mock()
    app.apps_status = Mock()
    app._show_toast = Mock()
    monkeypatch.setattr(panacea_ui.os, 'startfile', Mock(side_effect=OSError('unavailable')), raising=False)
    app.run_launch('ms-settings:appsfeatures', 'Apps settings')
    assert 'Failed' in app.operation_label.configure.call_args.kwargs['text']
    assert 'unavailable' in app.apps_status.configure.call_args.kwargs['text']


def test_resurrection_stops_after_command_completion_becomes_unknown():
    app = app_without_window()
    def timed_out(*args, **kwargs):
        app.cmd_runner.completion_unknown = True
        return False
    app.cmd_runner.run_command_stream.side_effect = timed_out
    result = app._run_resurrection_sequence()
    assert result['status'] == 'partial'
    assert len(result['steps']) == 5
    assert 'unknown' in result['steps'][-1]['message'].lower()
    app.disk_opt.analyze_optimize_drive.assert_not_called()


def test_unknown_command_completion_blocks_further_maintenance():
    app = app_without_window()
    app._update_installing = False
    app._maintenance_uncertain = True
    app._show_toast = Mock()
    assert app._request_operation('Another repair', Mock()) is False
    assert 'restart' in app._show_toast.call_args.args[1].lower()


def test_component_cleanup_routes_command_output_to_cleanup_details(monkeypatch):
    app = app_without_window()
    app.log_msg = Mock()
    app.log_tools_msg = Mock()
    app._show_result = Mock()
    app._request_operation = lambda name, work, done, **kwargs: done(work())
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', lambda *args, **kwargs: True)
    app.cmd_runner.run_command_stream.side_effect = lambda cmd, name, callback: callback('fixture output') or True
    app.run_deep_clean()
    app.log_msg.assert_any_call('fixture output')
    app.log_tools_msg.assert_not_called()


@pytest.mark.parametrize('raises', [False, True])
def test_timeout_guard_is_saved_before_result_delivery_and_blocks_reopen(tmp_path, raises):
    from modules.maintenance_guard import MaintenanceGuard
    app = app_without_window()
    app._update_installing = False
    app._maintenance_controls = []
    app.operation_label = Mock()
    app._show_toast = Mock()
    path = tmp_path / 'guard'
    app.maintenance_guard = MaintenanceGuard(path, lambda: 'windows-boot-id:10')
    def work():
        app.cmd_runner.completion_unknown = True
        if raises:
            raise RuntimeError('fixture failed after timeout')
        return False
    assert app._request_operation('fixture command', work)
    app.workers.join(3)
    assert MaintenanceGuard(path, lambda: 'windows-boot-id:10').is_blocked()
    app.dispatcher.drain()
    assert app._maintenance_uncertain
    assert 'restart' in app.operation_label.configure.call_args.kwargs['text'].lower()
    assert app._request_operation('Another command', Mock()) is False


def test_timeout_guard_save_failure_stays_visible_and_blocks_session():
    app = app_without_window()
    app._update_installing = False
    app._maintenance_controls = []
    app.operation_label = Mock()
    app._show_toast = Mock()
    app.maintenance_guard = SimpleNamespace(mark_unknown=Mock(return_value=False), last_error='Could not save the recovery guard: denied')
    def work():
        app.disk_opt.completion_unknown = True
        return False
    assert app._request_operation('fixture timeout', work)
    app.workers.join(3)
    app.dispatcher.drain()
    app.maintenance_guard.mark_unknown.assert_called_once()
    assert app._maintenance_uncertain
    assert 'Could not save' in app.operation_label.configure.call_args.kwargs['text']


@isolated_tk_test
def test_real_tk_keyboard_navigation_and_safe_control_activation(monkeypatch):
    app = _safe_real_app(monkeypatch)
    try:
        app.update()
        app.focus_force()
        for index, (name, _, _, _) in enumerate(app.NAV_GROUPS, 1):
            app.event_generate(f'<Control-Key-{index}>')
            app.update()
            assert app.active_frame == name
        app.select_frame('Tools')
        app.update()
        assert app.frame_tools.winfo_ismapped()
        assert app.frame_disk.winfo_ismapped()
        assert app.active_group == 'Tools'
        button = app.nav_buttons['Dashboard']
        button._canvas.focus_force()
        app.update()
        button._canvas.event_generate('<Return>')
        app.update()
        assert app.active_frame == 'Dashboard'
        button._canvas.event_generate('<Tab>')
        app.update()
        assert app.focus_get() != button._canvas
        app.select_frame('Disk')
        app._set_drives([{'letter': 'C:'}, {'letter': 'D:'}])
        app.update()
        app.drive_menu._canvas.focus_force()
        app.drive_menu._canvas.event_generate('<Down>')
        app.update()
        assert app.selected_drive.get() == 'D:'
        app.select_frame('Turbo')
        invoked = []
        switch = app.turbo_switches['power']
        switch.configure(state='normal', command=lambda: invoked.append(True))
        app.update()
        switch._canvas.focus_force()
        switch._canvas.event_generate('<space>')
        app.update()
        assert invoked == [True]
        switch.configure(state='disabled')
        switch._canvas.event_generate('<Return>')
        app.update()
        assert invoked == [True]
    finally:
        _destroy_real_app(app)


@isolated_tk_test
def test_real_tk_cleanup_output_keyboard_scroll_and_navigation_persist(monkeypatch):
    panacea_ui.ctk.set_widget_scaling(1.5)
    panacea_ui.ctk.set_window_scaling(1)
    app = _safe_real_app(monkeypatch)
    entered, emit_late, late_sent, release = (threading.Event() for _ in range(4))
    runs = []

    def analyze(*, progress_callback):
        runs.append(True)
        for index in range(60):
            progress_callback(f'Fixture analysis line {index}')
        entered.set()
        assert emit_late.wait(5)
        progress_callback('Fixture late message')
        late_sent.set()
        assert release.wait(5)
        return 7, 1572864

    def activate(button):
        button._canvas.focus_force()
        app.update()
        button._canvas.event_generate('<Return>')
        app.update()

    try:
        app.cleanup_mgr.preview_temp_files = analyze
        app.cleanup_mgr.last_result = SimpleNamespace(errors=[], skipped=[], skipped_counts={})
        app.update()
        panacea_ui.tk.Tk.maxsize(app, 1366, 768)
        panacea_ui.tk.Tk.geometry(app, '1366x768')
        app.select_frame('Cleaning')
        app._toggle_cleanup_tools()
        app.update()
        log = app.clean_log
        toggle = next(button for button in log.master.winfo_children() if isinstance(button, panacea_ui.ctk.CTkButton))
        assert not log.winfo_manager()
        # Analysis remains accessible from Overview, not the individual-cleanup panel.
        app.select_frame('Dashboard')
        app.update()
        analyze_button = next(button for button in _native_widgets(app.card_sys, panacea_ui.ctk.CTkButton)
                              if button.cget('text') == 'Analyze')
        activate(analyze_button)
        assert entered.wait(3)
        app.dispatcher.drain()
        app.select_frame('Cleaning')
        app.update()
        assert log.winfo_ismapped(), 'Accepted analysis must automatically open its live output'
        assert 'Fixture analysis line 59' in log.get('1.0', 'end')
        viewport = app.group_scroll['Cleaning']._parent_canvas
        assert _native_bounds(log)[3] <= _native_bounds(viewport)[3] + 2, (
            f'Opened output lies below the viewport: log={_native_bounds(log)}, '
            f'viewport={_native_bounds(viewport)}, scroll={viewport.yview()}')
        log._textbox.focus_force()
        app.update()
        before = log._textbox.yview()
        log._textbox.event_generate('<Prior>')
        app.update()
        assert log._textbox.yview()[0] < before[0], 'Keyboard PageUp must scroll readable output'
        reading_position = log._textbox.yview()
        app.event_generate('<Control-Key-1>')
        app.update()
        assert app.active_frame == 'Dashboard'
        app.event_generate('<Control-Key-2>')
        app.update()
        assert app.active_frame == 'Cleaning'
        assert log.winfo_ismapped()
        assert log._textbox.yview() == pytest.approx(reading_position)
        activate(toggle)
        assert not log.winfo_manager()
        emit_late.set()
        assert late_sent.wait(3)
        app.dispatcher.drain()
        app.update()
        assert not log.winfo_manager(), 'Late worker output must respect a manual close'
        release.set()
        app.workers.join(3)
        app.dispatcher.drain()
        app.update()
        assert not app.workers.busy()
        assert not log.winfo_manager(), 'Completion must preserve manual closure'
        assert 'Analysis completed' in app.dash_preview_status.cget('text')
        app.select_frame('Dashboard')
        app.update()
        activate(analyze_button)
        app.workers.join(3)
        app.dispatcher.drain()
        app.update()
        assert len(runs) == 2
        app.select_frame('Cleaning')
        app.update()
        assert log.winfo_ismapped(), 'A new explicit run must reopen output and leave it open at completion'
        app.select_frame('Dashboard')
        app.select_frame('Cleaning')
        app.update()
        assert log.winfo_ismapped()
    finally:
        emit_late.set()
        release.set()
        app.workers.join(3)
        _destroy_real_app(app)
        panacea_ui.ctk.set_widget_scaling(1)
        panacea_ui.ctk.set_window_scaling(1)


@isolated_tk_test
def test_paired_panels_are_both_visible_without_subnavigation(monkeypatch):
    app = _safe_real_app(monkeypatch)
    try:
        for group, pages in (
            ('Cleaning', ('Cleaning', 'Apps')),
            ('Tools', ('Tools', 'Disk')),
            ('Turbo', ('Turbo', 'Startup')),
        ):
            app.select_frame(group)
            app.update()
            host = app.group_frames[group]
            assert host.winfo_ismapped()
            assert not hasattr(app, 'subnav_frames')
            assert all(app.frames[page].winfo_ismapped() for page in pages)
            assert app.frames[pages[0]].winfo_rooty() < app.frames[pages[1]].winfo_rooty()
            assert app.frames[pages[0]].master is app.frames[pages[1]].master
            assert app.frames[pages[0]].master is app.group_scroll[group]
            assert not any(isinstance(widget, panacea_ui.ctk.CTkScrollableFrame)
                           for page in pages for widget in app.frames[page].winfo_children())
    finally:
        _destroy_real_app(app)


@isolated_tk_test
def test_real_tk_italian_ui_and_confirmation_follow_installer_choice(monkeypatch):
    # A temporary override simulates the Italian language chosen by setup;
    # the real installed build uses its protected panacea-language.ini instead.
    monkeypatch.setenv('PANACEA_LANGUAGE', 'italian')
    app = _safe_real_app(monkeypatch)
    try:
        app.update()
        assert app.language == 'it'
        assert 'Manutenzione del sistema' in app.title()
        assert app.brand_tagline.cget('text') == 'SYSTEM MAINTENANCE'
        assert app.nav_buttons['Cleaning'].cget('text') == 'Spazio e pulizia'
        assert app.nav_buttons['Resurrect'].cget('text') == 'Manutenzione guidata'
        assert not app.btn_check_update.winfo_manager()
        assert app.footer_credit.cget('text') == 'Panacea 2026 — Maurizio Falconi (falker47)'
        app.select_frame('Cleaning')
        app.update()
        assert app.frame_apps.winfo_ismapped()
        assert app.quick_cleanup_button.cget('text') == 'Avvia pulizia rapida'
        app.select_frame('Tools')
        app.update()
        assert app.frame_disk.winfo_ismapped()
        seen = []
        monkeypatch.setattr(panacea_ui.messagebox, 'askyesno',
                            lambda title, detail, **kwargs: (seen.append((title, detail)), False)[1])
        app.run_empty_recycle()
        assert len(seen) == 1
        assert 'cestino' in seen[0][0].casefold()
        assert 'Eliminare definitivamente' in seen[0][1]
        assert not app.workers.busy()
    finally:
        _destroy_real_app(app)

def _mock_update_check(monkeypatch, release=None, error=None):
    """Exercise UI state without downloading a release or opening Tk."""
    from modules import updater
    app = app_without_window()
    app._update_installing = False
    app.app_update_status = Mock()
    app.btn_check_update = Mock()
    app.btn_update_install = Mock()
    app.update_actions = Mock()
    app.workers = Mock()
    app.workers.busy.return_value = False
    client = Mock()
    if error is not None:
        client.check.side_effect = RuntimeError(error)
    else:
        client.check.return_value = release
    monkeypatch.setattr(updater, 'UpdateClient', lambda *args: client)

    def start(name, operation, **callbacks):
        try:
            callbacks['on_success'](operation())
        except Exception as exc:
            callbacks['on_error'](exc)
        callbacks['on_done']()

    app.workers.start.side_effect = start
    app._check_app_update()
    return app


def test_update_footer_has_no_actions_when_already_current(monkeypatch):
    app = _mock_update_check(monkeypatch)
    app.app_update_status.configure.assert_any_call(
        text='Panacea is already up to date.', text_color=panacea_ui.MUTED)
    app.update_actions.grid.assert_not_called()
    app.btn_check_update.grid.assert_not_called()


def test_update_footer_has_only_install_action_for_available_release(monkeypatch):
    release = SimpleNamespace(version='2.0.3')
    app = _mock_update_check(monkeypatch, release=release)
    app.app_update_status.configure.assert_any_call(
        text=f'You are using Panacea {panacea_ui.VERSION}. Update to version 2.0.3 is available.',
        text_color=panacea_ui.COL_BLUE)
    app.btn_update_install.configure.assert_any_call(state='normal', text='Install update')
    app.update_actions.grid.assert_called_once()
    app.btn_check_update.grid.assert_not_called()


def test_update_footer_offers_retry_only_after_check_error(monkeypatch):
    app = _mock_update_check(monkeypatch, error='network offline')
    app.update_actions.grid.assert_not_called()
    app.btn_check_update.grid.assert_called_once()
    app.app_update_status.configure.assert_any_call(
        text='Update check failed: network offline', text_color=panacea_ui.COL_WARNING)

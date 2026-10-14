"""Cleanup consent/results and output-panel lifecycle with inert Windows backends."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import panacea_ui
from modules.cleanup import CleanupResult
from test_ui_controller import app_without_window


class Widget:
    def __init__(self, **settings):
        self.settings = {'state': 'normal', 'text': '', **settings}
        self.manager = ''
        self.lines = []

    def configure(self, **settings):
        self.settings.update(settings)

    def cget(self, name):
        return self.settings[name]

    def pack(self, **kwargs):
        self.manager = 'pack'

    def pack_forget(self):
        self.manager = ''

    def grid(self, **kwargs):
        self.manager = 'grid'

    def grid_forget(self):
        self.manager = ''

    def winfo_manager(self):
        return self.manager

    def winfo_exists(self):
        return True

    def set(self, value):
        self.settings['value'] = value


@pytest.fixture
def app():
    subject = app_without_window()
    subject._update_installing = False
    subject._maintenance_uncertain = False
    subject._maintenance_controls = []
    subject._pending_logs = {}
    subject._preview_summary = 'Not analyzed yet'
    subject.operation_label = Widget()
    subject.preview_label = Widget()
    subject.dash_preview_status = Widget()
    subject._show_toast = Mock()
    subject._card = lambda parent: Widget()
    subject._create_log_textbox = lambda parent, **kwargs: Widget()
    subject._button = lambda parent, text, command, **kwargs: Widget(text=text, command=command)
    subject._append_log = lambda widget, message, level: widget.lines.append(message)
    subject.log_msg = lambda message: subject._log_section('clean_log', message)
    subject.cleanup_mgr.preview_temp_files = Mock(return_value=(7, 1572864))
    subject.cleanup_mgr.last_result = SimpleNamespace(errors=[], skipped=[], skipped_counts={})
    subject._test_releases = []
    yield subject
    for release in subject._test_releases:
        release.set()
    subject.workers.join(3)
    subject.dispatcher.drain()
    subject.workers.close()


def complete(app):
    app.workers.join(3)
    app.dispatcher.drain()
    assert not app.workers.busy()


def visible_result(app):
    return ' '.join(widget.cget('text') for widget in
                    (app.operation_label, app.preview_label, app.dash_preview_status)).lower()


def pending_operation(app, **kwargs):
    entered, release = threading.Event(), threading.Event()
    app._test_releases.append(release)
    def work():
        entered.set()
        assert release.wait(3), 'Fixture operation was not released'
        return True
    assert app._request_operation('Fixture operation', work, **kwargs)
    assert entered.wait(3)
    return release


def test_analysis_is_read_only_and_shows_potential_recovery_not_freed_space(app, monkeypatch):
    log = app._section_log(None, 'clean_log')
    confirmation = Mock(return_value=False)
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', confirmation)
    app.run_preview_temp()
    complete(app)
    result = visible_result(app)
    assert 'analysis completed' in result
    assert 'no files deleted' in result
    assert '7 candidates' in result
    assert 'about' in result and '1.5' in result and 'recoverable' in result
    assert 'freed' not in result
    confirmation.assert_not_called()
    app.cleanup_mgr.preview_temp_files.assert_called_once()
    app.cleanup_mgr.clean_temp_files.assert_not_called()
    assert log.winfo_manager()


def test_clean_now_can_run_without_analysis_but_still_requires_confirmation(app, monkeypatch):
    log = app._section_log(None, 'clean_log')
    confirmation = Mock(return_value=True)
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', confirmation)
    app.run_clean_temp()
    complete(app)
    confirmation.assert_called_once()
    app.cleanup_mgr.preview_temp_files.assert_not_called()
    app.cleanup_mgr.clean_temp_files.assert_called_once()
    result = visible_result(app)
    assert 'cleanup completed' in result
    assert '3 files deleted' in result and 'freed' in result
    assert log.winfo_manager()


@pytest.mark.parametrize('analyzed', [False, True])
def test_rejected_cleanup_never_deletes_and_analysis_never_grants_consent(app, monkeypatch, analyzed):
    log = app._section_log(None, 'clean_log')
    if analyzed:
        app.run_preview_temp()
        complete(app)
    app._set_section_log_open('clean_log', False)
    confirmation = Mock(return_value=False)
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', confirmation)
    app.run_clean_temp()
    complete(app)
    confirmation.assert_called_once()
    app.cleanup_mgr.clean_temp_files.assert_not_called()
    assert not log.winfo_manager()


def test_partial_analysis_keeps_no_deletion_and_reason_counts_explicit(app):
    app.cleanup_mgr.last_result = SimpleNamespace(
        errors=['Cannot inspect folder'], skipped=['Locked file'], skipped_counts={'locked': 1})
    app.run_preview_temp()
    complete(app)
    result = visible_result(app)
    assert 'analysis partial' in result
    assert 'no files deleted' in result
    assert '1 skipped' in result and ('1 error' in result or 'errors: 1' in result)
    app.cleanup_mgr.clean_temp_files.assert_not_called()


def test_failed_analysis_does_not_leave_a_completed_or_running_result(app):
    app.cleanup_mgr.preview_temp_files.side_effect = PermissionError('Fixture unavailable')
    app.run_preview_temp()
    complete(app)
    result = visible_result(app)
    assert 'failed' in result
    assert 'no files deleted' in result
    assert 'running' not in result and 'analysis completed' not in result
    app.cleanup_mgr.clean_temp_files.assert_not_called()
    app._show_toast.assert_called()


def test_partial_cleanup_uses_actual_deleted_count_and_freed_bytes(app, monkeypatch):
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', lambda *args, **kwargs: True)
    app.cleanup_mgr.clean_temp_files.return_value = (2, 2097152)
    app.cleanup_mgr.last_result = SimpleNamespace(
        errors=['Denied entry'], skipped=['Locked entry'], skipped_counts={'locked': 1})
    app.run_clean_temp()
    complete(app)
    result = visible_result(app)
    assert 'cleanup partial' in result
    assert '2 files deleted' in result and '2.0 mb freed' in result
    assert '1 skipped' in result and ('1 error' in result or 'errors: 1' in result)
    assert 'cleanup completed' not in result


@pytest.mark.parametrize('preview', [False, True])
def test_zero_progress_with_recorded_errors_is_failed_not_completed(app, monkeypatch, preview):
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', lambda *args, **kwargs: True)
    app.cleanup_mgr.last_result = SimpleNamespace(errors=['Cannot inspect root'], skipped=[], skipped_counts={})
    app.cleanup_mgr.preview_temp_files.return_value = (0, 0)
    app.cleanup_mgr.clean_temp_files.return_value = (0, 0)
    (app.run_preview_temp if preview else app.run_clean_temp)()
    complete(app)
    result = visible_result(app)
    assert ('analysis failed' if preview else 'cleanup failed') in result
    assert 'completed' not in result


def test_view_reasons_keeps_all_original_diagnostics_beyond_live_log_limit(app, monkeypatch):
    skipped = [f'Locked fixture entry {index}' for index in range(550)]
    errors = [f'Denied fixture entry {index}' for index in range(550)]
    details = SimpleNamespace(skipped=skipped.copy(), errors=errors.copy(), skipped_counts={'locked': 550})
    app.cleanup_mgr.last_result = details
    app.cleanup_reasons_button = Widget(state='disabled')
    app.run_preview_temp()
    complete(app)
    snapshot = app._cleanup_diagnostics
    assert isinstance(snapshot, tuple)
    assert len(snapshot) > app.LOG_LINES
    assert all(f'SKIPPED · {item}' in snapshot for item in skipped)
    assert all(f'ERROR · {item}' in snapshot for item in errors)
    assert app.cleanup_reasons_button.cget('state') == 'normal'
    # A subsequent backend result cannot mutate the details already presented.
    details.skipped[:] = ['Later backend entry']
    details.errors.clear()
    details.skipped_counts.clear()
    app.cleanup_mgr.last_result = SimpleNamespace(skipped=[], errors=[], skipped_counts={})
    assert app._cleanup_diagnostics == snapshot
    dialog, textbox = Mock(), Mock()
    monkeypatch.setattr(panacea_ui.ctk, 'CTkToplevel', lambda *args, **kwargs: dialog)
    monkeypatch.setattr(panacea_ui.ctk, 'CTkTextbox', lambda *args, **kwargs: textbox)
    app._font = Mock()
    app._show_cleanup_diagnostics()
    textbox.insert.assert_called_once_with('1.0', '\n'.join(snapshot))
    textbox.configure.assert_called_with(state='disabled')


@pytest.mark.parametrize('attribute', ['clean_log', 'disk_log', 'tools_log', 'god_log'])
def test_output_starts_closed_then_opens_for_an_accepted_explicit_operation(app, attribute):
    log = app._section_log(None, attribute)
    assert not log.winfo_manager()
    release = pending_operation(app, output=attribute)
    assert log.winfo_manager()
    release.set()
    complete(app)
    assert log.winfo_manager(), 'Completion must not hide the operation output'


def test_manual_close_survives_messages_and_next_accepted_operation_reopens(app):
    log = app._section_log(None, 'tools_log')
    release = pending_operation(app, output='tools_log')
    app._set_section_log_open('tools_log', False)
    app._log_section('tools_log', 'First streamed line')
    app.dispatcher.drain()
    assert log.lines == ['First streamed line']
    assert not log.winfo_manager(), 'Log delivery must respect the manual close'
    release.set()
    complete(app)
    assert not log.winfo_manager()
    release = pending_operation(app, output='tools_log')
    assert log.winfo_manager()
    release.set()
    complete(app)


def test_rejected_concurrent_operation_does_not_reopen_manually_closed_output(app):
    log = app._section_log(None, 'tools_log')
    release = pending_operation(app)
    rejected_work = Mock()
    assert app._request_operation('Rejected operation', rejected_work, output='tools_log') is False
    assert not log.winfo_manager()
    rejected_work.assert_not_called()
    release.set()
    complete(app)


def test_background_messages_do_not_open_a_lazily_created_output(app):
    app._log_section('clean_log', 'Background message before first navigation')
    app.dispatcher.drain()
    log = app._section_log(None, 'clean_log')
    assert log.lines == ['Background message before first navigation']
    assert not log.winfo_manager()


def test_explicit_operation_open_is_remembered_until_lazy_section_is_built(app):
    app._open_operation_output('clean_log')
    app._log_section('clean_log', 'Accepted operation before first navigation')
    app.dispatcher.drain()
    log = app._section_log(None, 'clean_log')
    assert log.winfo_manager()
    assert log.lines == ['Accepted operation before first navigation']


@pytest.mark.parametrize('opened', [False, True])
def test_navigation_preserves_manual_output_visibility(app, opened):
    log = app._section_log(None, 'clean_log')
    app._set_section_log_open('clean_log', opened)
    app.frames = {'Cleaning': Widget(), 'Tools': Widget()}
    app.nav_buttons = {name: Widget() for name in app.frames}
    app._built_frames = set(app.frames)
    app._setup_functions = {}
    app.select_frame('Tools')
    app.select_frame('Cleaning')
    assert bool(log.winfo_manager()) is opened


@pytest.mark.parametrize(('action', 'attribute'), [
    ('tools', 'tools_log'), ('disk', 'disk_log'),
    ('resurrection', 'god_log'), ('component', 'clean_log'),
])
def test_real_action_routes_accepted_start_to_its_output(app, monkeypatch, action, attribute):
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', lambda *args, **kwargs: True)
    log = app._section_log(None, attribute)
    if action == 'tools':
        app.run_cmd('ipconfig /flushdns', 'DNS flush')
    elif action == 'disk':
        app.selected_drive = SimpleNamespace(get=lambda: 'C:')
        app._drive_values = ['C:']
        app.run_optimize_drive()
    elif action == 'component':
        app.run_deep_clean()
    else:
        import modules.commands
        monkeypatch.setattr(modules.commands, 'system_executable', lambda name: 'C:\\Windows\\System32\\' + name)
        app.btn_resurrect_start = Widget()
        app.btn_resurrect_cancel = Widget()
        app.lbl_status = Widget()
        app.progress_bar = Widget()
        app.run_god_mode()
    complete(app)
    assert log.winfo_manager()


@pytest.mark.parametrize('preview', [False, True])
def test_failed_new_run_replaces_previous_analysis_diagnostics(app, monkeypatch, preview):
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', lambda *args, **kwargs: True)
    app.cleanup_reasons_button = Widget(state='disabled')
    previous = CleanupResult(count=7, bytes=1572864, skipped=['PREVIOUS analysis skipped item'], preview=True)
    app.cleanup_mgr.last_result = previous
    app.run_preview_temp()
    complete(app)
    assert any('PREVIOUS' in line for line in app._cleanup_diagnostics)

    # Failure before the backend initializes a fresh result must not recycle
    # the prior analysis counts or reasons as evidence of this new operation.
    backend = app.cleanup_mgr.preview_temp_files if preview else app.cleanup_mgr.clean_temp_files
    backend.side_effect = PermissionError('CURRENT operation could not start')
    (app.run_preview_temp if preview else app.run_clean_temp)()
    complete(app)
    result = visible_result(app)
    snapshot = '\n'.join(app._cleanup_diagnostics)
    assert 'CURRENT operation could not start' in snapshot
    assert 'PREVIOUS' not in snapshot
    assert '7 candidates' not in result and '7 files deleted' not in result
    assert 'completed' not in result and 'running' not in result
    assert app.cleanup_reasons_button.cget('state') == 'normal'
    if preview:
        assert 'analysis failed' in result and 'no files deleted' in result
    else:
        assert 'cleanup interrupted' in result or 'cleanup failed' in result


def test_interrupted_cleanup_keeps_only_actual_current_pass_counts_and_reasons(app, monkeypatch):
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', lambda *args, **kwargs: True)
    app.cleanup_mgr.last_result = CleanupResult(count=99, bytes=99 * 1048576,
                                               skipped=['PREVIOUS analysis item'], preview=True)
    app.run_preview_temp()
    complete(app)
    def interrupted(**kwargs):
        app.cleanup_mgr.last_result = CleanupResult(count=2, bytes=2097152,
            skipped=['CURRENT locked item'], errors=['CURRENT inspection error'])
        raise RuntimeError('CURRENT unexpected interruption')
    app.cleanup_mgr.clean_temp_files.side_effect = interrupted
    app.run_clean_temp()
    complete(app)
    result = visible_result(app)
    snapshot = '\n'.join(app._cleanup_diagnostics)
    assert '2 files deleted' in result and '2.0 mb freed' in result
    assert 'cleanup interrupted' in result or 'cleanup failed' in result
    assert 'cleanup completed' not in result
    assert 'PREVIOUS' not in snapshot
    for detail in ('CURRENT locked item', 'CURRENT inspection error', 'CURRENT unexpected interruption'):
        assert detail in snapshot


@pytest.mark.parametrize('action', ['restore', 'battery'])
@pytest.mark.parametrize('fails', [False, True])
def test_tools_secondary_actions_open_output_and_record_success_or_failure(app, monkeypatch, action, fails):
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', lambda *args, **kwargs: True)
    log = app._section_log(None, 'tools_log')
    if action == 'restore':
        backend = app.restore_mgr.create_restore_point
        backend.return_value = (True, 'Verified fixture restore point')
        run = app.run_create_restore
    else:
        backend = Mock()
        monkeypatch.setattr(panacea_ui.subprocess, 'run', backend)
        monkeypatch.setattr('modules.commands.system_executable', lambda name: 'C:\\Fixture\\' + name)
        monkeypatch.setattr(panacea_ui.os, 'startfile', Mock())
        run = app.run_battery_report
    if fails:
        backend.side_effect = RuntimeError('Fixture operation failure')
    run()
    complete(app)
    backend.assert_called_once()
    assert log.winfo_manager(), 'Accepted Tools actions must open their output'
    output = '\n'.join(log.lines).lower()
    assert ('restore point' if action == 'restore' else 'battery report') in output
    if fails:
        assert 'fixture operation failure' in output
        assert 'failed' in output
    else:
        assert 'completed' in output or 'saved' in output

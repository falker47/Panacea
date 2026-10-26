"""User-confirmed quick cleanup with inert managers (never touches host Windows)."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import panacea_ui
from modules.operations import OperationResult, StepResult
from modules.quick_cleanup import COMPONENT_CLEANUP, run_quick_cleanup
from panacea_ui import PanaceaApp
from test_ui_controller import app_without_window


def fake_managers():
    record = SimpleNamespace(preview=False, skipped=[], errors=[])
    cleanup = SimpleNamespace(
        last_result=record,
        clean_temp_files=Mock(return_value=(12, 2097152)),
        empty_recycle_bin=Mock(return_value=(True, 'Emptied')),
        open_disk_cleanup=Mock(return_value=True),
    )
    commands = SimpleNamespace(
        completion_unknown=False, restart_required=False,
        run_command_stream=Mock(return_value=True),
    )
    return cleanup, commands


def test_quick_cleanup_runs_three_guarded_operations_in_order_and_reports_attempts():
    cleanup, commands = fake_managers()
    order = []
    cleanup.clean_temp_files.side_effect = lambda **kw: (
        order.append('temp') or 12, 2097152)
    cleanup.empty_recycle_bin.side_effect = lambda: (order.append('bin') or True, 'Done')
    commands.run_command_stream.side_effect = lambda cmd, name, cb: (
        order.append('dism') or True)
    progress = []
    result = run_quick_cleanup(
        cleanup, commands, Mock(), progress=lambda done, total, step:
        progress.append((done, total, step.name, step.success)))
    assert order == ['temp', 'bin', 'dism']
    assert result.status == 'completed'
    assert [step.name for step in result.steps] == [
        'Temporary files', 'Recycle Bin', 'Component store']
    assert progress == [
        (1, 3, 'Temporary files', True),
        (2, 3, 'Recycle Bin', True),
        (3, 3, 'Component store', True),
    ]
    assert commands.run_command_stream.call_args.args[:2] == (
        COMPONENT_CLEANUP, 'Component store cleanup')
    cleanup.open_disk_cleanup.assert_not_called()  # Launch belongs to UI only.


def test_skipped_temporary_files_are_reported_partial_and_do_not_skip_other_steps():
    cleanup, commands = fake_managers()
    cleanup.last_result.skipped = ['locked']
    result = run_quick_cleanup(cleanup, commands, Mock())
    assert result.status == 'partial'
    assert [step.success for step in result.steps] == [False, True, True]
    assert '1 skipped' in result.steps[0].message


def test_unverified_temporary_file_results_do_not_claim_success():
    cleanup, commands = fake_managers()
    cleanup.last_result = None
    result = run_quick_cleanup(cleanup, commands, Mock())
    assert result.status == 'partial'
    assert 'could not be verified' in result.steps[0].message


def test_cancel_between_steps_does_not_run_recycle_bin_or_dism():
    cleanup, commands = fake_managers()
    cancel = threading.Event()
    def temp(**kwargs):
        cancel.set()
        return 12, 2097152
    cleanup.clean_temp_files.side_effect = temp
    result = run_quick_cleanup(cleanup, commands, Mock(), cancel=cancel)
    assert result.status == 'cancelled'
    assert [step.name for step in result.steps] == ['Temporary files']
    cleanup.empty_recycle_bin.assert_not_called()
    commands.run_command_stream.assert_not_called()


def fake_ui():
    app = app_without_window()
    cleanup, commands = fake_managers()
    app.cleanup_mgr, app.cmd_runner = cleanup, commands
    app.operation_label = Mock()
    app._quick_cleanup_cancel = threading.Event()
    app.quick_cleanup_bar = Mock()
    app.quick_cleanup_status = Mock()
    app._set_section_log_open = Mock()
    app._request_operation = Mock(return_value=True)
    app._show_toast = Mock()
    app._update_installing = False
    app._update_downloading = False
    return app


def test_quick_cleanup_denied_confirmation_runs_nothing(monkeypatch):
    app = fake_ui()
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', lambda *a, **kw: False)
    assert app.run_quick_cleanup() is False
    app._request_operation.assert_not_called()
    app.cleanup_mgr.clean_temp_files.assert_not_called()
    app.cleanup_mgr.empty_recycle_bin.assert_not_called()


def test_quick_cleanup_confirmation_is_explicit_and_accepted_once(monkeypatch):
    app = fake_ui()
    confirmations = []
    def confirm(*args, **kwargs):
        confirmations.append((args, kwargs))
        return True
    monkeypatch.setattr(panacea_ui.messagebox, 'askyesno', confirm)
    assert app.run_quick_cleanup() is True
    assert len(confirmations) == 1
    notice = confirmations[0][0][1]
    assert 'ENTIRE Recycle Bin' in notice
    assert 'OPEN Windows Disk Cleanup' in notice
    assert 'irreversible' in notice
    app._request_operation.assert_called_once()
    app.cleanup_mgr.clean_temp_files.assert_not_called()


def test_ui_launches_windows_cleanup_only_after_three_finished_steps():
    app = fake_ui()
    app.log_msg = Mock()
    result = OperationResult('completed', [
        StepResult('Temporary files', True, 'removed 12'),
        StepResult('Recycle Bin', True, 'emptied'),
        StepResult('Component store', True, 'done')])
    app._finish_quick_cleanup(result)
    app.cleanup_mgr.open_disk_cleanup.assert_called_once()
    status = app.quick_cleanup_status.configure.call_args.kwargs['text']
    assert 'opened' in status and 'manual' not in status.lower().split('opened')[0]
    assert 'choose and confirm' in status
    assert '4/4 completed' not in status


def test_ui_does_not_launch_windows_cleanup_if_cancelled_or_completion_unknown():
    for state in ('cancelled', 'unknown'):
        app = fake_ui()
        app.log_msg = Mock()
        if state == 'unknown':
            app.cmd_runner.completion_unknown = True
        else:
            app._quick_cleanup_cancel.set()
        result = OperationResult('partial', [
            StepResult('Temporary files', True, 'done'),
            StepResult('Recycle Bin', True, 'done'),
            StepResult('Component store', False, 'failure')])
        app._finish_quick_cleanup(result)
        app.cleanup_mgr.open_disk_cleanup.assert_not_called()
        assert 'not opened' in app.quick_cleanup_status.configure.call_args.kwargs['text']


def test_windows_cleanup_launch_error_stays_visible():
    app = fake_ui()
    app.log_msg = Mock()
    app.cleanup_mgr.open_disk_cleanup.return_value = False
    result = OperationResult('completed', [
        StepResult('Temporary files', True, 'done'),
        StepResult('Recycle Bin', True, 'done'),
        StepResult('Component store', True, 'done')])
    app._finish_quick_cleanup(result)
    assert 'launch failed' in app.quick_cleanup_status.configure.call_args.kwargs['text']
    assert app.operation_label.configure.call_args.kwargs['text_color'] == panacea_ui.COL_WARNING


def test_resurrection_explanations_have_one_entry_per_actual_step():
    assert set(PanaceaApp.RESURRECTION_HELP) == set(PanaceaApp.RESURRECTION_STEPS)
    assert 'Deleted files are NOT recoverable' in PanaceaApp.RESURRECTION_HELP['Restore point']

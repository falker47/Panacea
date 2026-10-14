import threading

import modules.operations as operations


def test_failed_critical_restore_never_runs_destructive_step():
    touched = []
    result = operations.run_sequence([
        operations.OperationStep('Restore', lambda: (False, 'unverified'), critical=True),
        operations.OperationStep('Delete caches', lambda: touched.append('deleted') or True),
    ])
    assert result.status == 'failed'
    assert touched == []
    assert [(step.name, step.success, step.message) for step in result.steps] == [('Restore', False, 'unverified')]


def test_noncritical_failure_reports_partial_and_advances_after_completion():
    progress = []
    executed = []
    def first():
        assert progress == []
        executed.append('first')
        return True
    result = operations.run_sequence([
        operations.OperationStep('First', first),
        operations.OperationStep('Failed', lambda: (False, 'exit 5')),
        operations.OperationStep('Last', lambda: executed.append('last') or True),
    ], progress=lambda done, total, step: progress.append((done, total, step.success)))
    assert result.status == 'partial'
    assert executed == ['first', 'last']
    assert progress == [(1, 3, True), (2, 3, False), (3, 3, True)]


def test_cancellation_waits_until_command_finishes_and_stops_next_step():
    cancel = threading.Event()
    executed = []
    def first():
        cancel.set()
        executed.append('first finished')
        return True
    result = operations.run_sequence([
        operations.OperationStep('First', first),
        operations.OperationStep('Next', lambda: executed.append('next') or True),
    ], cancel=cancel)
    assert result.status == 'cancelled'
    assert executed == ['first finished']
    assert len(result.steps) == 1 and result.steps[0].success


def test_exception_and_unknown_result_are_failures():
    def crash(): raise OSError('denied')
    result = operations.run_sequence([
        operations.OperationStep('Crash', crash),
        operations.OperationStep('Unknown', lambda: None),
    ])
    assert result.status == 'failed'
    assert all(not step.success for step in result.steps)
    assert 'denied' in result.steps[0].message


def test_all_success_reports_completed():
    result = operations.run_sequence([operations.OperationStep('Done', lambda: (True, 'verified'))])
    assert result.status == 'completed'
    assert result.steps[0].message == 'verified'


def test_progress_exception_stops_before_next_command():
    touched = []
    def crash(*args): raise RuntimeError('UI callback unavailable')
    result = operations.run_sequence([
        operations.OperationStep('Done', lambda: True),
        operations.OperationStep('Next', lambda: touched.append('ran') or True),
    ], progress=crash)
    assert result.status == 'partial'
    assert len(result.steps) == 1
    assert 'UI callback unavailable' in result.error
    assert touched == []


def test_cancellation_check_failure_preserves_completed_steps_and_stops_sequence():
    executed = []
    def cancellation():
        if executed:
            raise RuntimeError('Cancellation state unavailable')
        return False
    result = operations.run_sequence([
        operations.OperationStep('First', lambda: executed.append('first') or True),
        operations.OperationStep('Next', lambda: executed.append('next') or True),
    ], cancel=cancellation)
    assert result.status == 'partial'
    assert executed == ['first']
    assert len(result.steps) == 1 and result.steps[0].success
    assert 'Cancellation state unavailable' in result.error

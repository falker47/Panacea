import importlib
import threading


def dispatcher():
    module = importlib.import_module('modules.ui_dispatch')
    return module.UiDispatcher, module.WorkerController


def test_callbacks_are_delivered_only_by_owner_thread():
    UiDispatcher, _ = dispatcher()
    queue = UiDispatcher()
    calls = []
    worker = threading.Thread(target=lambda: queue.post(lambda: calls.append(threading.get_ident())))
    worker.start(); worker.join()
    assert calls == []
    assert queue.drain() == 1
    assert calls == [threading.get_ident()]


def test_queue_is_bounded_and_latest_key_replaces_old_value():
    UiDispatcher, _ = dispatcher()
    queue = UiDispatcher(max_pending=3)
    calls = []
    for value in range(10):
        queue.post(calls.append, value, key='metrics')
    assert queue.pending == 1
    for value in range(10):
        queue.post(calls.append, value)
    assert queue.pending == 3
    queue.drain()
    assert calls == [7, 8, 9]


def test_shutdown_discards_pending_and_late_callbacks():
    UiDispatcher, _ = dispatcher()
    queue = UiDispatcher()
    calls = []
    queue.post(calls.append, 'pending')
    queue.close()
    assert queue.post(calls.append, 'late') is False
    assert queue.drain() == 0
    assert calls == []


def test_worker_holds_group_until_completion_delivered():
    UiDispatcher, WorkerController = dispatcher()
    queue = UiDispatcher()
    workers = WorkerController(queue)
    entered, release = threading.Event(), threading.Event()
    calls = []
    def work():
        entered.set(); release.wait(2)
        return 'done'
    assert workers.start('clean', work, on_success=calls.append)
    assert entered.wait(2)
    assert not workers.start('turbo', lambda: None)
    release.set(); workers.join(2)
    assert not workers.start('clean', lambda: None)
    assert calls == []
    queue.drain()
    assert calls == ['done']
    assert workers.start('turbo', lambda: None)
    workers.join(2); queue.drain()


def test_worker_exception_releases_guard_and_delivers_done_on_main_thread():
    UiDispatcher, WorkerController = dispatcher()
    queue = UiDispatcher()
    workers = WorkerController(queue)
    calls = []
    def work():
        raise ValueError('offline')
    workers.start('check', work, on_error=lambda exc: calls.append(str(exc)), on_done=lambda: calls.append('reset'))
    workers.join(2)
    assert calls == []
    queue.drain()
    assert calls == ['offline', 'reset']
    assert not workers.busy('maintenance')


def test_drain_rejects_non_owner_and_isolates_callback_errors():
    UiDispatcher, _ = dispatcher()
    queue = UiDispatcher()
    errors, calls = [], []
    thread = threading.Thread(target=lambda: errors.append(_capture(queue.drain)))
    thread.start(); thread.join()
    assert isinstance(errors[0], RuntimeError)
    queue.post(lambda: 1 / 0)
    queue.post(calls.append, 'still delivered')
    assert queue.drain() == 2
    assert calls == ['still delivered']


def _capture(fn):
    try:
        fn()
    except Exception as exc:
        return exc

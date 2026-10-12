"""Bounded worker-to-UI delivery without importing or calling Tk."""
from collections import deque
import logging
import threading
import time


class UiDispatcher:
    def __init__(self, max_pending=512):
        self._owner = threading.get_ident()
        self._lock = threading.Lock()
        self._items = deque()
        self._limit = max(1, max_pending)
        self._closed = False

    @property
    def pending(self):
        with self._lock:
            return len(self._items)

    def post(self, callback, *args, key=None, critical=False):
        with self._lock:
            if self._closed:
                return False
            if key is not None:
                self._items = deque(item for item in self._items if item[2] != key)
            if len(self._items) >= self._limit:
                # Preserve operation completion; discard oldest expendable update/log.
                removable = next((i for i, item in enumerate(self._items) if not item[3]), None)
                if removable is None:
                    return False
                del self._items[removable]
            self._items.append((callback, args, key, critical))
            return True

    def drain(self, limit=100):
        if threading.get_ident() != self._owner:
            raise RuntimeError("UI callbacks must be drained on the owner thread")
        delivered = 0
        while delivered < limit:
            with self._lock:
                if self._closed or not self._items:
                    break
                callback, args, _, _ = self._items.popleft()
            try:
                callback(*args)
            except Exception:
                logging.getLogger(__name__).exception("UI callback failed")
            delivered += 1
        return delivered

    def close(self):
        with self._lock:
            self._closed = True
            self._items.clear()


class WorkerController:
    """Hold each operation group until its result reaches the main thread."""
    def __init__(self, dispatcher):
        self.dispatcher = dispatcher
        self._lock = threading.Lock()
        self._active = {}
        self._threads = set()
        self._closed = False

    def busy(self, group="maintenance"):
        with self._lock:
            return group in self._active

    def start(self, name, work, *, group="maintenance", on_success=None, on_error=None, on_done=None):
        with self._lock:
            if self._closed or group in self._active:
                return False
            self._active[group] = name

        def complete(result, error):
            try:
                if error is not None:
                    if on_error:
                        on_error(error)
                elif on_success:
                    on_success(result)
            finally:
                with self._lock:
                    self._active.pop(group, None)
                if on_done:
                    on_done()

        def run():
            result, error = None, None
            try:
                result = work()
            except Exception as exc:
                error = exc
            finally:
                self.dispatcher.post(complete, result, error, critical=True)
                with self._lock:
                    self._threads.discard(threading.current_thread())

        thread = threading.Thread(target=run, name=f"panacea-{name}", daemon=True)
        with self._lock:
            self._threads.add(thread)
        thread.start()
        return True

    def close(self):
        with self._lock:
            self._closed = True
        self.dispatcher.close()

    def join(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._lock:
            threads = tuple(self._threads)
        for thread in threads:
            remaining = None if deadline is None else max(0, deadline - time.monotonic())
            thread.join(remaining)

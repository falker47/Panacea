"""Process-wide Python, native and QML crash reporting for the Qt application."""
import faulthandler
import os
import sys
import threading
import traceback
from uuid import uuid4

from modules import logger


class CrashCapture:
    def __init__(self, folder):
        self.folder = folder
        self.marker = folder / "crash-marker.log"
        self.stream = None
        self.previous_size = 0
        self.previous_crash = False
        self._hooks = None

    def install(self):
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler

        if self._hooks:
            return
        with logger.storage_lock(self.folder.parent), logger.directory(self.folder, create=True):
            self.stream = logger.open_regular(self.marker, "ab", buffering=0)
        self.previous_size = self.stream.seek(0, os.SEEK_END)
        try:
            with logger.open_regular(self.folder / "crash-seen", "rb") as seen:
                acknowledged = int(seen.read(25))
        except (OSError, ValueError):
            acknowledged = 0
        self.previous_crash = self.previous_size > 0 and self.previous_size != acknowledged

        previous_sys, previous_thread = sys.excepthook, threading.excepthook
        def python_hook(kind, value, tb):
            try:
                self._report("main", kind, value, tb)
            finally:
                previous_sys(kind, value, tb)

        def thread_hook(args):
            try:
                self._report("thread", args.exc_type, args.exc_value, args.exc_traceback)
            finally:
                previous_thread(args)

        def qt_hook(kind, context, message):
            try:
                if kind in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
                    logger.Logger().log("Qt warning: " + str(message), "WARNING")
            finally:
                if previous_qt is not None:
                    previous_qt(kind, context, message)
                elif sys.stderr is not None:
                    print(message, file=sys.stderr)

        previous_qt = None
        was_enabled = faulthandler.is_enabled()
        try:
            # A fatal exception cannot safely run Python callbacks. The native
            # traceback itself grows the same marker observed by the next launch.
            faulthandler.enable(file=self.stream, all_threads=True)
            previous_qt = qInstallMessageHandler(qt_hook)
        except BaseException:
            self.stream.close()
            self.stream = None
            raise
        sys.excepthook, threading.excepthook = python_hook, thread_hook
        self._hooks = (previous_sys, previous_thread, previous_qt, was_enabled)

    def _report(self, source, kind, value, tb):
        if issubclass(kind, (SystemExit, KeyboardInterrupt)):
            return
        try:
            self.stream.write(("Unhandled Python exception: " + source + "\n").encode("ascii"))
            os.fsync(self.stream.fileno())
            logger.Logger().log("Unhandled Python exception: " + source + "\n"
                                + "".join(traceback.format_exception(kind, value, tb)), "ERROR")
        except Exception:
            pass  # Always chain the previously installed hook.

    def dismiss(self):
        if not self.previous_crash:
            return
        with logger.directory(self.folder):
            temporary = self.folder / ("crash-seen-" + uuid4().hex + ".tmp")
            with logger.open_regular(temporary, "xb") as stream:
                stream.write(str(self.previous_size).encode("ascii"))
                stream.flush()
                os.fsync(stream.fileno())
            logger.replace_sibling(temporary, "crash-seen")
        self.previous_crash = False

    def close(self):
        if not self._hooks:
            return
        from PySide6.QtCore import qInstallMessageHandler
        sys.excepthook, threading.excepthook, previous_qt, was_enabled = self._hooks
        qInstallMessageHandler(previous_qt)
        faulthandler.disable()
        if was_enabled and sys.stderr is not None:
            faulthandler.enable()
        self.stream.close()
        self.stream = self._hooks = None


_capture = None


def install():
    global _capture
    if _capture is None:
        capture = CrashCapture(logger.data_directory() / "logs")
        capture.install()
        _capture = capture
    return _capture

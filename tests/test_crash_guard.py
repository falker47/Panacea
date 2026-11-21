import faulthandler
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6 import QtCore

from modules import crash_guard, logger


def test_python_thread_qt_and_native_reports_offer_next_start_banner(tmp_path, monkeypatch):
    folder = tmp_path / "Panacea/logs"
    monkeypatch.setattr(logger, "known_folder", lambda name: tmp_path)
    # Observe the actual hook inputs without faulting or killing the test process.
    native = Mock()
    monkeypatch.setattr(faulthandler, "enable", native)
    monkeypatch.setattr(faulthandler, "is_enabled", lambda: False)
    monkeypatch.setattr(faulthandler, "disable", Mock())
    previous_qt = Mock()
    qt_install = Mock(return_value=previous_qt)
    monkeypatch.setattr(QtCore, "qInstallMessageHandler", qt_install)
    main, worker = Mock(), Mock()
    monkeypatch.setattr(sys, "excepthook", main)
    monkeypatch.setattr(threading, "excepthook", worker)
    sink = Mock()
    monkeypatch.setattr(logger, "Logger", lambda: sink)
    first = crash_guard.CrashCapture(folder)
    first.install()
    try:
        assert not first.previous_crash
        native.assert_called_once_with(file=first.stream, all_threads=True)
        error = RuntimeError("fixture report")
        sys.excepthook(type(error), error, None)
        args = SimpleNamespace(exc_type=type(error), exc_value=error, exc_traceback=None)
        threading.excepthook(args)
        main.assert_called_once_with(type(error), error, None)
        worker.assert_called_once_with(args)
        qt_install.call_args.args[0](QtCore.QtMsgType.QtWarningMsg, None, "fixture QML warning")
        previous_qt.assert_called_once()
        messages = [call.args[0] for call in sink.log.call_args_list]
        assert any("main" in m and "fixture report" in m for m in messages)
        assert any("thread" in m and "fixture report" in m for m in messages)
        assert any("fixture QML warning" in m for m in messages)
        assert b"main" in first.marker.read_bytes() and b"thread" in first.marker.read_bytes()
    finally:
        first.close()
    second = crash_guard.CrashCapture(folder)
    second.install()
    try:
        assert second.previous_crash
        second.dismiss()
        assert not second.previous_crash
    finally:
        second.close()
    third = crash_guard.CrashCapture(folder)
    third.install()
    try:
        assert not third.previous_crash
        native.call_args.kwargs["file"].write(b"Fatal Python error: native fixture\n")
    finally:
        third.close()
    fourth = crash_guard.CrashCapture(folder)
    fourth.install()
    try:
        assert fourth.previous_crash
    finally:
        fourth.close()

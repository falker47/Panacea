"""Load actual feature components in fresh offscreen Qt GUI processes."""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def probe(language):
    from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, Qt, qInstallMessageHandler, QtMsgType
    from PySide6.QtGui import QAccessible, QGuiApplication
    from PySide6.QtQuick import QQuickView
    from PySide6.QtTest import QTest

    from modules.diagnostics import FILES
    from modules.maintenance_guard import _state

    if os.name == "nt":
        from modules.commands import system_executable
        os.environ["QT_QPA_FONTDIR"] = str(Path(system_executable("cmd.exe")).parents[1] / "Fonts")
    app = QGuiApplication([])
    warnings = []
    def report(kind, context, message):
        if kind in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            warnings.append(message)
    previous = qInstallMessageHandler(report)

    class Recovery(QObject):
        changed = Signal()
        def __init__(self):
            super().__init__()
            self.state = _state("interrupted_journal")
            self.crashed = True
            self.confirmed = []
            self.exported = 0
        guardState = Property("QVariantMap", lambda self: self.state, notify=changed)
        previousCrash = Property(bool, lambda self: self.crashed, notify=changed)
        busy = Property(bool, lambda self: False, constant=True)
        notice = Property(str, lambda self: "", constant=True)
        diagnosticFiles = Property("QStringList", lambda self: list(FILES), constant=True)

        @Slot(result=str)
        def prepareArchive(self):
            return "test-one-use"
        @Slot(str, result=bool)
        def confirmArchive(self, nonce):
            self.confirmed.append(nonce)
            return True
        @Slot()
        def cancelArchive(self):
            pass
        @Slot()
        def verifyAgain(self):
            pass
        @Slot()
        def dismissCrash(self):
            self.crashed = False
            self.changed.emit()
        @Slot()
        def exportDiagnostics(self):
            self.exported += 1

    class History(QObject):
        changed = Signal()
        def __init__(self):
            super().__init__()
            self.data = {"items": [], "corrupt": 0, "total": 0, "unavailable": False, "has_more": False}
            self.requests = []
        pageData = Property("QVariantMap", lambda self: self.data, notify=changed)
        busy = Property(bool, lambda self: False, constant=True)
        @Slot(int, str)
        def loadPage(self, offset, status):
            self.requests.append((offset, status))

    recovery, history = Recovery(), History()
    def items(parent):
        yield parent
        for child in parent.childItems():
            yield from items(child)
    def texts(root):
        return [item.property("text") for item in items(root) if item.isVisible() and item.inherits("QQuickText")]
    def controls(root):
        return [item for item in items(root) if item.isVisible()
                and (item.inherits("QQuickAbstractButton") or item.inherits("QQuickComboBox"))]
    def check_access(root):
        for item in controls(root):
            interface = QAccessible.queryAccessibleInterface(item)
            assert interface and interface.text(QAccessible.Text.Name), item
            assert interface.role() in (QAccessible.Role.Button, QAccessible.Role.ComboBox), interface.role()
            assert item.activeFocusOnTab(), item
        for item in items(root):
            if item.isVisible() and item.inherits("QQuickText"):
                assert item.property("font").pixelSize() >= 12, (item.property("text"), item.property("font"))
    def click(root, text):
        item = next(x for x in controls(root) if x.property("text") == text)
        item.forceActiveFocus()
        QTest.keyClick(view, Qt.Key.Key_Space)
        app.processEvents()

    try:
        for component in ("RecoveryBanner", "History"):
            view = QQuickView()
            view.rootContext().setContextProperty("reliabilityService", recovery)
            view.rootContext().setContextProperty("historyService", history)
            view.engine().warnings.connect(lambda faults: warnings.extend(e.toString() for e in faults))
            view.setInitialProperties({"language": language})
            view.setSource(QUrl.fromLocalFile(str(ROOT / "qt_app/qml/features" / (component + ".qml"))))
            assert view.status() == QQuickView.Status.Ready, [error.toString() for error in view.errors()]
            root = view.rootObject()
            root.setWidth(440)
            view.resize(440, 650)
            view.show()
            app.processEvents()
            it = language == "it"
            if component == "RecoveryBanner":
                click(root, "Archivia e sblocca" if it else "Archive and unblock")
                assert not recovery.confirmed
                check_access(root)
                click(root, "Conferma archiviazione" if it else "Confirm archive")
                assert recovery.confirmed == ["test-one-use"]
                click(root, "Esporta diagnostica" if it else "Export diagnostics")
                assert all(any(name in line for line in texts(root)) for name in FILES)
                assert recovery.exported == 0
                click(root, "Salva ZIP in Download" if it else "Save ZIP to Downloads")
                assert recovery.exported == 1
                recovery.state = _state("clear")
                recovery.changed.emit()
                assert root.isVisible()
                click(root, "Ignora avviso di arresto" if it else "Dismiss crash notice")
                assert not root.isVisible() and root.implicitHeight() == 0
            else:
                assert history.requests == [(0, "")]
                assert any(("appariranno" if it else "will appear") in text for text in texts(root))
                row = {"action": "sfc", "status": "completed", "success": True, "started": "2026-01-01T10:00:00Z",
                       "finished": "2026-01-01T10:01:00Z", "id": "1"*32, "app_version": "2.1.1", "bytes": 42}
                history.data.update(items=[row], total=1)
                history.changed.emit()
                app.processEvents()
                click(root, "Dettagli" if it else "Details")
                assert any("42" in text and "2.1.1" in text for text in texts(root))
                check_access(root)
                combo = next(item for item in controls(root) if item.objectName() == "historyFilter")
                combo.forceActiveFocus()
                QTest.keyClick(view, Qt.Key.Key_Down)
                app.processEvents()
                assert history.requests[-1] == (0, "completed"), history.requests
            view.close()
            view.setSource(QUrl())
            app.processEvents()
        assert not warnings, warnings
    finally:
        qInstallMessageHandler(previous)


class ReliabilityQmlTests(unittest.TestCase):
    def test_italian_and_english_offscreen(self):
        for language in ("it", "en"):
            with self.subTest(language=language):
                result = subprocess.run(
                    [sys.executable, "-c", "from qt_app.tests.test_reliability_qml import probe; "
                     "import sys; probe(sys.argv[1])", language],
                    cwd=ROOT, env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_CONTROLS_STYLE": "Basic"},
                    capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

"""Optional extension registration is explicit and distinguishes missing dependencies."""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject

from qt_app.bridges import KNOWN_EXTENSIONS, load_extensions


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        self.qml = Mock()
        self.qml.contextProperty.return_value = None
        self.context = SimpleNamespace(qml_context=self.qml, reader=Mock(), updater=Mock(), maintenance=Mock(),
                                       metrics=Mock(), language=lambda: "en", qa_smoke=True)

    def test_present_module_receives_live_context_and_missing_peer_is_skipped(self):
        self.assertEqual(KNOWN_EXTENSIONS, ("reliability", "features"))
        obj = QObject()
        create = Mock(return_value={"historyService": obj})
        absent = ModuleNotFoundError(name="qt_app.bridges.features_bridge")
        with patch("qt_app.bridges.import_module", side_effect=[SimpleNamespace(create=create), absent]) as imported:
            objects = load_extensions(self.context)
        self.assertEqual([x.args[0] for x in imported.call_args_list],
                         ["qt_app.bridges.reliability_bridge", "qt_app.bridges.features_bridge"])
        create.assert_called_once_with(self.context)
        self.qml.setContextProperty.assert_called_once_with("historyService", obj)
        self.assertIs(objects["historyService"], obj)

    def test_missing_dependency_in_installed_extension_is_not_treated_as_absent(self):
        with patch("qt_app.bridges.import_module", side_effect=ModuleNotFoundError(name="nested_dependency")):
            with self.assertRaises(ModuleNotFoundError):
                load_extensions(self.context)
        self.qml.setContextProperty.assert_not_called()

    def test_duplicate_registration_does_not_replace_the_real_maintenance_bridge(self):
        self.qml.contextProperty.return_value = self.context.maintenance
        module = SimpleNamespace(create=lambda _: {"maintenanceService": QObject()})
        with patch("qt_app.bridges.import_module", return_value=module), self.assertRaises(ValueError):
            load_extensions(self.context)
        self.qml.setContextProperty.assert_not_called()

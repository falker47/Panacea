"""Pure contract checks. Real Windows launch is covered by the isolated workflow."""

from pathlib import Path
import unittest

LAB = Path(__file__).resolve().parents[1]


class QtLabContract(unittest.TestCase):
    def test_live_history_keeps_all_sixty_legacy_plot_positions(self):
        from PySide6.QtCore import QCoreApplication
        from qt_lab.main import MetricsBridge
        app = QCoreApplication.instance() or QCoreApplication([])
        bridge = MetricsBridge()
        try:
            for value in range(65):
                bridge._apply({"cpu": f"{value}.0%", "ram": "—", "disk": "—"})
            self.assertEqual(bridge.cpuHistory, list(range(5, 65)))
            app.processEvents()
        finally:
            bridge.stop()

    def test_five_pages_are_named(self):
        qml = (LAB / "Main.qml").read_text(encoding="utf-8")
        for page in ("Dashboard", "Cleaning", "Tools", "Turbo", "Resurrect"):
            self.assertIn('name: "' + page + '"', qml)
        self.assertIn("property var visited:", qml)
        self.assertIn("active: shell.visited[index]", qml)

    def test_no_maintenance_mutation_surface(self):
        qml = (LAB / "Main.qml").read_text(encoding="utf-8")
        self.assertIn("FUNZIONI DI SISTEMA DISABILITATE", qml)
        self.assertNotIn("onClicked: bridge.", qml)
        self.assertNotIn("onClicked: liveMetrics.", qml)
        runner = (LAB / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("from modules.cleanup import", runner)
        self.assertNotIn("from modules.performance import", runner)
        self.assertNotIn("from modules.update_install import", runner)

    def test_legacy_metric_fixture_preserves_real_measurement_fields(self):
        from qt_lab.main import _format_sample
        sample = _format_sample({
            "cpu": 30.8, "ram": (16.0, 1.5, 90.7),
            "disk": (256.0, 6.4, 97.5),
            "battery": (72, "Plugged In"), "uptime": "0d 3h 8m",
        })
        self.assertEqual(sample["details"]["ram"], [16.0, 1.5, 90.7])
        self.assertEqual(sample["details"]["disk"], [256.0, 6.4, 97.5])
        self.assertEqual(sample["details"]["battery"], 72)
        self.assertEqual(sample["details"]["uptime"], "0d 3h 8m")
        invalid = _format_sample({"cpu": None, "ram": None, "disk": (0, -1, 105)})
        self.assertEqual(invalid["details"]["ram"], [None, None, None])
        self.assertEqual(invalid["details"]["disk"], [None, None, None])

    def test_qml_and_runner_exist(self):
        self.assertTrue((LAB / "Main.qml").is_file())
        self.assertTrue((LAB / "main.py").is_file())
        self.assertIn("--smoke-test", (LAB / "main.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

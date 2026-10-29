"""Pure contract checks. Real Windows launch is covered by the isolated workflow."""

from pathlib import Path
import unittest

LAB = Path(__file__).resolve().parents[1]


class QtLabContract(unittest.TestCase):
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

    def test_qml_and_runner_exist(self):
        self.assertTrue((LAB / "Main.qml").is_file())
        self.assertTrue((LAB / "main.py").is_file())
        self.assertIn("--smoke-test", (LAB / "main.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

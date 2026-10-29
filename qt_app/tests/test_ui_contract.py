"""Visible Qt migration affordances must match current backend capabilities."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UiContractTests(unittest.TestCase):
    def test_qa_shell_is_explicitly_not_an_updater_or_maintenance_ui(self):
        qml = (ROOT / "Main.qml").read_text(encoding="utf-8")
        self.assertIn("COMANDI DI SISTEMA DISABILITATI", qml)
        self.assertIn("readService.request", qml)
        self.assertIn("readService.busy", qml)
        self.assertNotIn("maintenanceBridge.execute", qml)

    def test_packaging_entrypoint_stays_distinct_from_stable_main(self):
        app = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn("Panacea Qt UI migration QA", app)
        self.assertNotIn("run_update_helper(", app)
        self.assertNotIn("ShellExecuteW(", app)

    def test_five_primary_destinations_survive(self):
        qml = (ROOT / "Main.qml").read_text(encoding="utf-8")
        for section in ("Dashboard", "Cleaning", "Tools", "Turbo", "Resurrect"):
            self.assertIn('name: "' + section + '"', qml)


if __name__ == "__main__":
    unittest.main()

"""The Qt guided-maintenance surface preserves V2 per-phase details.

Tests are presentation-only: no Windows maintenance is invoked.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
QML = ROOT / "qt_app" / "ParityPage.qml"
V2 = ROOT / "panacea_ui.py"


class ResurrectionVisualParityTests(unittest.TestCase):
    def test_all_legacy_phases_have_explanations_and_stable_order(self):
        qml = QML.read_text(encoding="utf-8")
        stable = V2.read_text(encoding="utf-8")
        source = stable.split("RESURRECTION_HELP = {", 1)[1].split("\n    }", 1)[0]
        original_keys = [
            "Restore point", "Browser caches", "Temporary files", "Recycle Bin",
            "DNS cache", "Network reset", "Drive optimization", "Disk health scan",
            "Windows image health", "System file scan",
        ]
        self.assertEqual(len(original_keys), 10)
        for key in original_keys:
            self.assertIn("'" + key + "':", source)
        self.assertIn("objectName: \"resurrection_step_\" + index", qml)
        self.assertIn("Accessible.description: guidedStep.helpCopy", qml)
        self.assertIn("progressSteps[modelData].message", qml)
        self.assertIn('progressSteps[modelData].success === true ? "#78c8a8" : "#ee939a"', qml)
        self.assertIn("view.stepCaption(modelData)", qml)
        guided_model = qml.split("id: stepGrid", 1)[1].split("id: guidedStep", 1)[0]
        self.assertEqual(guided_model.count("help:"), 9)
        self.assertIn('title: view.language === "it" ? "Cache e temporanei"', guided_model)
        self.assertIn('help: view.language === "it" ?', guided_model)
        self.assertIn('operations: [1, 2]', qml)
        self.assertEqual(qml.count('operations: ['), 9)
        self.assertIn('readonly property int backendIndex: modelData', qml)
        self.assertIn('9 passaggi · 10 operazioni', qml)
        self.assertIn("guidedStep.expanded = !guidedStep.expanded", qml)
        self.assertIn("Keys.onSpacePressed: activate()", qml)


if __name__ == "__main__":
    unittest.main()

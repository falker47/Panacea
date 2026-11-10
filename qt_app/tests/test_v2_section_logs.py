"""Original V2 tool logs stay with their respective views."""
from pathlib import Path
import unittest


class V2ActivityLogParity(unittest.TestCase):
    def test_every_original_log_is_collocated(self):
        qml = (Path(__file__).resolve().parents[1] / "ParityPage.qml").read_text(encoding="utf-8")
        self.assertEqual(qml.count("PSectionLog {"), 4)
        for title in ("Cleanup details", "Command output", "Optimization output", "Full sequence output"):
            self.assertIn(title, qml)
        self.assertIn("maintenanceService.sectionLogs[sectionLog.scope]", qml)
        self.assertIn("readService.sectionLogs[sectionLog.scope]", qml)
        self.assertIn("maintenanceService.cancel()", qml)
        self.assertIn("sectionLog.expanded = !sectionLog.expanded", qml)
        self.assertIn("contentHeight: logText.implicitHeight", qml)
        self.assertIn("height: sectionLog.expanded ? 160 : 0", qml)
        self.assertIn('readonly property string rawOutput:', qml)
        self.assertIn('sectionLog.showFullOutput ? sectionLog.rawOutput : view.compactConsoleLog(sectionLog.rawOutput)', qml)
        self.assertIn('objectName: "consoleSurface_" + sectionLog.scope', qml)
        self.assertIn('color: "#050505"', qml)
        self.assertIn('objectName: "consoleFullToggle_" + sectionLog.scope', qml)
        self.assertNotIn("property bool logExpanded:", qml)


if __name__ == "__main__":
    unittest.main()

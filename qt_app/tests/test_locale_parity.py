"""Qt must use the V2 installer language precedence rather than Qt locale guessing."""
from pathlib import Path
import tempfile
import unittest

from modules.localization import LOCALE_FILE, resolve_language


ROOT = Path(__file__).resolve().parents[1]


class LocaleParityContracts(unittest.TestCase):
    def test_installer_language_overrides_windows_and_environment_in_qt(self):
        with tempfile.TemporaryDirectory() as location:
            exe = Path(location) / "PanaceaQtCandidate.exe"
            (Path(location) / LOCALE_FILE).write_text(
                "[Panacea]\nLanguage=italian\n", encoding="utf-8"
            )
            self.assertEqual(resolve_language(
                executable=exe, system_language="en_US", override="english"
            ), "it")

    def test_shell_receives_canonical_locale_from_python(self):
        app = (ROOT / "main.py").read_text(encoding="utf-8")
        qml = (ROOT / "Main.qml").read_text(encoding="utf-8")
        self.assertIn('setContextProperty("applicationLanguage", resolve_language())', app)
        self.assertIn("property string language: applicationLanguage", qml)
        self.assertNotIn("property string language: Qt.locale()", qml)
        self.assertIn('onLanguageChanged: maintenanceService.setLanguage(language)', qml)


if __name__ == "__main__":
    unittest.main()

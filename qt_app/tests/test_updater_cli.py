"""Production-compatible Qt entrypoint must preserve protected updater protocol."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProtectedUpdateCliContracts(unittest.TestCase):
    def test_qt_entrypoint_supports_same_helper_and_readiness_arguments(self):
        qt = (ROOT / "main.py").read_text(encoding="utf-8")
        stable = (ROOT.parent / "main.py").read_text(encoding="utf-8")
        for flag in ("--panacea-update-helper", "--panacea-update-ready"):
            self.assertIn(flag, stable)
            self.assertIn(flag, qt)
        self.assertIn("run_update_helper(args.panacea_update_helper)", qt)
        self.assertIn("acknowledge_ready(sys.executable, args.panacea_update_ready)", qt)
        self.assertIn("QTimer.singleShot(250, acknowledge_update)", qt)

    def test_qa_executable_cannot_claim_production_readiness(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('Path(sys.executable).name != "Panacea.exe"', source)
        self.assertIn('if args.panacea_update_helper:', source)
        self.assertLess(source.index('if args.panacea_update_helper:'),
                        source.index("QGuiApplication([sys.argv[0]])"))
        self.assertNotIn("start_self_update(", source)
        self.assertIn('not getattr(sys, "frozen", False)', source)


if __name__ == "__main__":
    unittest.main()

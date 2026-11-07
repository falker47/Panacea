"""Old seven-entry screenshots must not masquerade as V2 2.0.2 references."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from qt_app.visual_review import current_reference_is_fresh


class StableSourceReferenceTests(unittest.TestCase):
    def test_current_reference_requires_source_hash_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "panacea_ui.py").write_text("live source", encoding="utf-8")
            ref = root / "observations.json"
            ref.write_text(json.dumps({
                "source_sha256": {
                    "panacea_ui.py": hashlib.sha256(b"live source").hexdigest()
                }
            }), encoding="utf-8")
            self.assertTrue(current_reference_is_fresh(ref, root))
            (root / "panacea_ui.py").write_text("changed source", encoding="utf-8")
            self.assertFalse(current_reference_is_fresh(ref, root))
            ref.write_text("broken JSON", encoding="utf-8")
            self.assertFalse(current_reference_is_fresh(ref, root))

    def test_qa_workflow_captures_real_stable_source(self):
        workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/qt-migration.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/visual_check.py", workflow)
        self.assertIn("--current-baseline build/qt-app/stable-v2-current-1366x768-100", workflow)


if __name__ == "__main__":
    unittest.main()

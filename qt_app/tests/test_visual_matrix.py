"""Every required desktop/locale/scale has original pixels and geometry evidence."""
from itertools import product
import json
from pathlib import Path
import tempfile
import unittest

from PySide6.QtGui import QImage

from qt_app.catalog import SECTIONS
from qt_app.parity_matrix import cases, verify_case
from qt_app.visual_review import source_digest


class VisualMatrixTests(unittest.TestCase):
    def test_each_section_language_scale_and_desktop_size_is_required(self):
        matrix = list(cases())
        expected = set(product(((760, 480), (1366, 768), (1920, 1080)), (100, 125, 150), ("en", "it")))
        self.assertEqual({(s, d, lang) for s, d, lang, _ in matrix}, expected)
        self.assertEqual(len(matrix) * len(SECTIONS), 162)
        for size, scale, _, logical in matrix:
            self.assertGreaterEqual(logical[0], 760)
            self.assertGreaterEqual(logical[1], 480)
            if size != (760, 480):
                self.assertLessEqual(abs(logical[0] * scale/100 - size[0]), 1)

    def test_wrong_dpi_or_warning_or_overflow_fails_even_with_valid_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = QImage(20, 20, QImage.Format.Format_RGB32)
            image.fill(0)
            for section in SECTIONS:
                image.save(str(root/(section+".png")))
                meta = dict(logical_size=[20, 20], image_size=[20, 20], language="en", section=section,
                            qml_warnings=[], geometry={"errors": [], "controls": [{"role":"Button","name":"fixture"}]},
                            visual_fixture=True, safe_mode=True, source_sha256="test")
                (root/(section+".json")).write_text(json.dumps(meta), encoding="utf-8")
            self.assertEqual(len(verify_case(root, (20, 20), 100, "en")), 9)
            with self.assertRaises(ValueError):
                verify_case(root, (20, 20), 150, "en")
            target = root/(section+".json")
            for changes in ({"qml_warnings": ["broken binding"]}, {"geometry": {"errors":["overflow"]}},
                            {"section":"other"}, {"visual_fixture":False}):
                target.write_text(json.dumps({**meta, **changes}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    verify_case(root, (20, 20), 100, "en")

    def test_digest_tracks_page_components_and_catalogs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("qml").mkdir()
            root.joinpath("i18n").mkdir()
            for path in ("Main.qml", "qml/Page.qml", "qml/qmldir", "i18n/en.json"):
                (root/path).write_text("a")
            for path in ("Main.qml", "qml/Page.qml", "qml/qmldir", "i18n/en.json"):
                before = source_digest(root)
                (root/path).write_text("b")
                self.assertNotEqual(source_digest(root), before)

    def test_ci_archives_full_matrix_and_runs_packaged_capture(self):
        workflow = (Path(__file__).resolve().parents[2]/".github/workflows/qt-migration.yml").read_text(encoding="utf-8")
        for token in ("qt_app/parity_matrix.py", "build/qt-matrix/**", "Panacea-Qt-Desktop-Matrix",
                      "Packaged Qt UI smoke and screenshot", "Repeat native source lifecycle"):
            self.assertIn(token, workflow)

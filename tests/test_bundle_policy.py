"""Exercise the archive policy on CArchiveReader-shaped TOCs, without building Qt."""
import os

import pytest

from scripts.packaged_probe import compare, peak_working_set
from scripts.verify_bundle import (
    MAX_EXE_BYTES, MAX_EXTRACTED_BYTES, REQUIRED, archive_report, denied, missing_required,
)


@pytest.mark.parametrize("name", [
    "Qt6WebEngineCore.dll", "qml/QtQuick/Controls/Windows/qmldir",
    r"PySide6\Qt6WebEngineCore.dll", "PySide6/qml/QtWebView/qmldir", "PySide6/QtQuick3D.pyd",
    "PySide6/plugins/imageformats/qpdf.dll", "PySide6/Qt63DCore.dll", "PySide6/qml/Qt3D/Core/qmldir",
    "PySide6/Qt6Multimedia.dll", "PySide6/plugins/platforminputcontexts/qtvirtualkeyboardplugin.dll",
    "PySide6/Qt6Charts.dll", "PySide6/Qt6Graphs.dll", "PySide6/Qt6DataVisualization.dll",
    "PySide6/Qt6Location.dll", "PySide6/Qt6Positioning.dll", "PySide6/Qt6TextToSpeech.dll",
    "PySide6/plugins/sqldrivers/qsqlite.dll", "PySide6/Qt6Bluetooth.dll", "PySide6/Qt6Designer.dll",
    "PySide6/qml/QtQuick/Controls/Imagine/qmldir", "PySide6/Qt6QuickControls2FusionStyleImpl.dll",
    "PySide6/qml/QtQuick/Controls/NewStyle/qmldir", "PySide6/translations/qtbase_fr.qm",
])
def test_denied_qt_families(name):
    assert denied(name)


def test_required_entries_locales_and_unrelated_python_extensions_survive():
    for name in (*REQUIRED, "PySide6/translations/qtbase_it.qm", "PySide6/translations/qtbase_en_GB.qm",
                 "PySide6/Qt6QuickControls2Impl.dll", "PySide6/qml/QtQuick/Controls/Basic/impl/qmldir",
                 "_sqlite3.pyd", "docs/pdf-reference.txt"):
        assert not denied(name)
    assert not missing_required(n.upper().replace("/", "\\") for n in REQUIRED)


def test_inventory_and_budget_boundaries():
    toc = {name: (0, i, 2 * i, 1, "b") for i, name in enumerate(REQUIRED, 1)}
    total = sum(r[2] for r in toc.values())
    toc["padding"] = (0, 10, MAX_EXTRACTED_BYTES - total, 1, "x")
    report = archive_report(toc, MAX_EXE_BYTES)
    assert not report["errors"] and not report["within_target"]
    assert report["extracted_bytes"] == MAX_EXTRACTED_BYTES
    assert report["compressed_bytes"] == sum(r[1] for r in toc.values())
    assert len(report["top_20_by_compressed_bytes"]) == 20
    assert report["top_20_by_compressed_bytes"][0]["name"] == REQUIRED[-1]
    forbidden = "PySide6/Qt6WebEngineCore.dll"
    toc[forbidden] = toc.pop(REQUIRED[0])
    toc["excess"] = (0, 1, 1, 0, "x")
    failed = archive_report(toc, MAX_EXE_BYTES + 1)
    assert failed["forbidden"] == [forbidden] and failed["missing"] == [REQUIRED[0]]
    assert len(failed["errors"]) == 3


@pytest.mark.parametrize(("entries", "modules", "expected"), [
    ([], ["PIL", "PIL.Image", "PILLOW_example"], ["PYZ.pyz:PIL", "PYZ.pyz:PIL.Image"]),
    ([r"PIL\_imaging.pyd", "pillow.libs/example.dll"], [], [r"PIL\_imaging.pyd", "pillow.libs/example.dll"]),
    (["assets/pill.png"], ["PILLOW_example"], []),
])
def test_frozen_pillow_modules_and_native_files(entries, modules, expected):
    toc = {name: (0, 1, 1, 0, "b") for name in (*REQUIRED, *entries)}
    report = archive_report(toc, MAX_EXE_BYTES, modules)
    assert report["forbidden"] == expected
    assert bool(report["errors"]) == bool(expected)


@pytest.mark.skipif(os.name != "nt", reason="Windows process memory counters")
def test_peak_working_set_for_current_fixture_process():
    assert peak_working_set(os.getpid()) > 0


def test_startup_ratio_budget_is_inclusive():
    assert compare(1.1, 1)["passed"]
    assert not compare(1.101, 1)["passed"]
    assert compare(0.8, 1)["improvement_percent"] == pytest.approx(20)

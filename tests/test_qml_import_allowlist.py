"""Application QML imports and the release archive policy are reviewed together."""
from pathlib import Path, PureWindowsPath
import re


ALLOWED = {
    "QtQuick", "QtQuick.Window", "QtQuick.Layouts", "QtQuick.Controls", "QtQuick.Controls.Basic",
    "QtQuick.Templates", "QtQuick.Effects", "QtQml",
}
# Preserve quoted paths and line numbers while removing QML comments.
TOKENS = re.compile(r'''("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(//[^\n]*|/\*[\s\S]*?\*/)''')
IMPORT = re.compile(r'''^\s*import\s+("[^"]*"|'[^']*'|[^\s;]+)''')


def unsupported_imports(source):
    cleaned = TOKENS.sub(lambda match: match[1] if match[1] else " " + "\n" * match[0].count("\n"), source)
    for line_number, line in enumerate(cleaned.splitlines(), 1):
        match = IMPORT.match(line)
        if not match:
            continue
        target = match[1]
        if target[:1] in {"'", '"'}:
            path = target[1:-1]
            if path and not PureWindowsPath(path).anchor and ":" not in path and "\\" not in path:
                continue
        elif target in ALLOWED:
            continue
        yield line_number, target


def test_application_qml_imports_match_release_policy():
    root = Path(__file__).resolve().parents[1]
    files = sorted((root / "qt_app").rglob("*.qml"))
    assert files, "No application QML found"
    issues = [f"{path.relative_to(root)}:{line}: {target}" for path in files
              for line, target in unsupported_imports(path.read_text(encoding="utf-8-sig"))]
    assert not issues, "Review Panacea.spec and the QML import allowlist together:\n" + "\n".join(issues)


def test_scanner_recognizes_versions_aliases_comments_and_local_directories():
    assert list(unsupported_imports('/* import QtCharts */\nimport QtQuick 2.15 as QQ\nimport "components" as UI')) == []
    assert list(unsupported_imports('import QtMultimedia 6.0\nimport "https://example.org/qml"')) == [
        (1, "QtMultimedia"), (2, '"https://example.org/qml"'),
    ]

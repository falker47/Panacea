"""Qt catalogs own shell copy and preserve the installer's first-run preference."""
from pathlib import Path
import re

import pytest

from modules.localization import LOCALE_FILE, resolve_language
from qt_app.i18n import messages


ROOT = Path(__file__).resolve().parents[1]


def test_language_precedence_for_installed_and_portable_qt(tmp_path, monkeypatch):
    exe = tmp_path / "Panacea.exe"
    sidecar = exe.with_name(LOCALE_FILE)
    sidecar.write_text("[Panacea]\nLanguage=italian\n", encoding="utf-8")
    monkeypatch.setenv("PANACEA_LANGUAGE", "english")
    arguments = {"executable": exe, "system_language": "en_US"}
    assert resolve_language(**arguments) == "it"
    assert resolve_language(user_choice="en", **arguments) == "en"
    assert resolve_language(user_choice="system", **arguments) == "en"
    monkeypatch.setenv("PANACEA_LANGUAGE", "italian")
    portable = {"executable": tmp_path / "portable" / "Panacea.exe", "system_language": "en_US"}
    assert resolve_language(**portable) == "it"
    monkeypatch.delenv("PANACEA_LANGUAGE")
    assert resolve_language(**portable) == "en"


def test_every_message_has_both_locales_and_matching_parameters():
    english, italian = messages("en"), messages("it")
    assert english.keys() == italian.keys()
    for key in english:
        assert english[key].strip() and italian[key].strip(), key
        assert set(re.findall(r"\{(\w+)\}", english[key])) == set(re.findall(r"\{(\w+)\}", italian[key])), key


# Check the values that reach a user-facing property, including ternary/fallback
# branches. Dotted catalog paths inside Theme.tr/i18n.t and identifiers passed
# to data accessors are expressions, not UI text.
_BINDING = re.compile(r"(?<![\w.])(?:Accessible\.(?:name|description)|(?:Basic\.)?ToolTip\.text|"
                      r"text|title|description|subtitle|placeholderText|displayText|caption|label|"
                      r"summary|heading|confirmText|statusText|message)\s*:\s*")
_LITERAL = re.compile(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\x60(?:\\.|[^\x60\\])*\x60''')
_BRAND = {"Panacea", "v"}


def _visible_copy(source):
    lines = source.splitlines()
    for index, line in enumerate(lines):
        for binding in _BINDING.finditer(line):
            if "property color " in line[:binding.start()]:
                continue
            expression = line[binding.end():]
            next_line = index + 1
            while next_line < len(lines) and (
                expression.rstrip().endswith(("?", ":", "||", "+", "(", ","))
                or lines[next_line].lstrip().startswith((":", "?", "||", "+"))
            ):
                expression += " " + lines[next_line]
                next_line += 1
            expression = expression.split(";")[0]
            for match in _LITERAL.finditer(expression):
                value = match[0][1:-1].strip()
                if not re.search(r"[^\W\d_]", value) or value in _BRAND:
                    continue
                prefix = expression[:match.start()].rstrip()
                if not prefix or prefix.endswith(("?", ":", "||", "??", "+")):
                    if "." in value and re.fullmatch(r"[\w.]+", value) and re.search(r"\b(?:tr|t)\(", prefix):
                        continue
                    yield index + 1, value


@pytest.mark.parametrize("source", [
    'Text { text: "Save" }', 'Accessible.name: "Open settings"',
    'description: active ? "Running" : tr("status.idle")',
    'title: tr("title.key") ||\n "Fallback"',
    'summary: ready ? tr("some.ready")\n : "Retry now"',
])
def test_qml_guard_detects_visible_literals(source):
    assert list(_visible_copy(source))


def test_qml_shell_has_no_hardcoded_visible_copy():
    files = [ROOT / "Main.qml", *(ROOT / "qml").rglob("*.qml")]
    offenders = [(str(path.relative_to(ROOT)), number, value)
                 for path in files if "features" not in path.relative_to(ROOT).parts
                 for number, value in _visible_copy(path.read_text(encoding="utf-8"))]
    assert offenders == []


def test_every_literal_translation_call_resolves_in_the_catalogs():
    static_call = re.compile(r'''\b(?:Theme\.tr|i18n\.t)\(\s*(["'])([^"'\n]+)\1\s*[,)]''')
    files = [ROOT / "Main.qml", *(ROOT / "qml").rglob("*.qml")]
    for path in files:
        if "features" in path.relative_to(ROOT).parts:
            continue
        for _, key in static_call.findall(path.read_text(encoding="utf-8")):
            assert key in messages("it") and key in messages("en"), (path, key)

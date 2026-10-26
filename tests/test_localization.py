"""The installer selection controls Panacea text, not only the setup wizard."""
from pathlib import Path

import pytest

from modules.localization import (
    LOCALE_FILE, read_installed_language, resolve_language, translate,
)


@pytest.mark.parametrize('choice,expected', [('italian', 'it'), ('english', 'en')])
def test_installed_language_is_preserved_and_overrides_system_locale(tmp_path, choice, expected):
    exe = tmp_path / 'Panacea.exe'
    exe.write_bytes(b'fixture only')
    (tmp_path / LOCALE_FILE).write_text(
        f'[Panacea]\nLanguage={choice}\n', encoding='utf-8')
    assert read_installed_language(exe) == expected
    assert resolve_language(executable=exe, system_language='en_US',
                            override='italian') == expected


def test_portable_uses_windows_language_when_no_installer_sidecar(tmp_path):
    exe = tmp_path / 'Panacea.exe'
    assert resolve_language(executable=exe, system_language='it_IT', override='') == 'it'
    assert resolve_language(executable=exe, system_language='en_US', override='') == 'en'


@pytest.mark.parametrize('bad', [
    '[Panacea]\nLanguage=unsupported\n',
    '[Other]\nLanguage=italian\n',
    'not a configuration',
])
def test_invalid_installer_language_falls_back_safely(tmp_path, bad):
    exe = tmp_path / 'Panacea.exe'
    (tmp_path / LOCALE_FILE).write_text(bad, encoding='utf-8')
    assert read_installed_language(exe) is None
    assert resolve_language(executable=exe, system_language='en_US', override='') == 'en'


def test_italian_translates_navigation_and_status_while_english_is_unchanged():
    assert translate('SYSTEM MAINTENANCE', 'it') == 'SYSTEM MAINTENANCE'
    assert translate('Panacea is already up to date.', 'it') == "Panacea è già aggiornato all'ultima versione."
    assert translate('Install update', 'it') == 'Installa aggiornamento'
    assert translate('You are using Panacea 2.0.2. Update to version 2.0.3 is available.', 'it') == "Stai usando Panacea 2.0.2. È disponibile l'aggiornamento alla versione 2.0.3."
    assert translate('Guided Maintenance', 'it') == 'Manutenzione guidata'
    assert translate('Resurrection', 'it') == 'Manutenzione guidata'
    assert translate('Confirm Guided Maintenance', 'it') == 'Conferma manutenzione guidata'
    assert translate('Maintenance steps', 'it') == 'Passaggi di manutenzione'
    assert translate('0 / 10 steps', 'it') == '0 / 10 passaggi'
    assert translate('10 / 10 steps', 'en') == '10 / 10 steps'
    assert translate('Space & Cleanup', 'it') == 'Spazio e pulizia'
    assert translate('Panacea 2.0.2 is up to date', 'it') == 'Panacea 2.0.2 è aggiornato'
    assert translate('Ready · No operation running', 'it') == 'Pronto · Nessuna operazione in corso'
    assert translate('Ready · No operation running', 'en') == 'Ready · No operation running'
    assert translate('sfc /scannow', 'it') == 'sfc /scannow'


def test_italian_confirmation_describes_irreversible_deletion():
    source = ('Permanently delete every item in the Recycle Bin?\n'
              'These items cannot be recovered through the Recycle Bin.')
    result = translate(source, 'italian')
    assert 'Eliminare definitivamente' in result
    assert 'Cestino' in result
    assert 'cannot' not in result


def test_italian_status_parts_are_localized_but_technical_tokens_survive():
    result = translate('Analysis completed\n12 candidates · about 1.5 MB recoverable\n'
                       '2 skipped · 0 errors', 'it')
    assert 'Analisi completata' in result
    assert '12 candidati' in result
    assert 'circa 1.5 MB recuperabili' in result
    assert '2 ignorati' in result
    assert '0 errori' in result


def test_installer_emits_language_sidecar_next_to_protected_exe():
    source = (Path(__file__).parents[1] / 'packaging' / 'Panacea.iss').read_text(encoding='utf-8')
    assert '[INI]' in source
    assert 'panacea-language.ini' in source
    assert 'String: "{language}"' in source
    assert 'Type: files; Name: "{app}\\panacea-language.ini"' in source

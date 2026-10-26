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


def test_compact_ux_copy_has_italian_translation_and_safe_maintenance_warning():
    for source in (
        'Manage or uninstall programs in Windows.',
        'Disable unnecessary apps at sign-in.',
        'Windows uses the appropriate optimization method for each drive.',
        'Open Windows drive optimizer',
        'Original settings are saved for restoration.',
        'Saved settings unavailable · Refresh state',
    ):
        assert translate(source, 'it') != source

    warning = (
        'Permanent deletion: browser caches, temporary files and Recycle Bin items; '
        'restore points cannot recover them.\n'
        'Network reset can interrupt connections or require restart. '
        'Save work; cancellation stops between steps.'
    )
    result = translate(warning, 'it')
    assert 'Eliminazione definitiva' in result
    assert 'punti di ripristino' in result
    assert 'annullamento' in result



def test_dashboard_power_and_guided_safety_are_fully_localized():
    from modules.localization import WARNINGS
    assert translate('Plugged In', 'it') == 'Collegato alla corrente'
    assert translate('On Battery', 'it') == 'Alimentazione a batteria'
    assert translate('Charging', 'it') == 'In carica'
    assert translate('Restart recommended', 'it') == 'Riavvio consigliato'
    assert translate('Browser cache', 'it') == 'Cache browser'
    assert translate('Temp files', 'it') == 'File temporanei'
    warning = next(k for k in WARNINGS if k.startswith('A new restore point must be verified first.'))
    translated = translate(warning, 'it')
    assert 'Prima di procedere' in translated
    assert 'termina il passaggio in corso' in translated
    assert 'non avvia i successivi' in translated


@pytest.mark.parametrize(('source', 'expected'), [
    ('Create restore point', 'Crea punto di ripristino'),
    ('Windows uses the appropriate optimization method for each drive.',
     'Windows usa il metodo di ottimizzazione adatto a ogni unità.'),
    ('No available updates', 'Nessun aggiornamento disponibile'),
    ('2 recommended, 1 optional', '2 consigliati, 1 facoltativo'),
    ('Run DISM repair?', 'Eseguire Riparazione DISM?'),
    ('Run Windows optimization on C:?', "Ottimizzare l'unità C: con Windows?"),
    ('3/10 finished · Restore point', '3/10 completati · Punto di ripristino'),
    ('Result: Restart required.', 'Risultato: Riavvio necessario.'),
    ('Quick cleanup failed: access denied', 'Pulizia rapida non riuscita: access denied'),
    ('Cancellation requested; the current command will finish.',
     "Annullamento richiesto: il comando in corso terminerà prima dell'arresto."),
])
def test_final_copy_audit_translates_actions_live_status_and_warnings(source, expected):
    assert translate(source, 'it') == expected
    assert translate(source, 'en') == source


def test_natural_dynamic_update_and_maintenance_text_never_mix_languages():
    assert translate('Download and verify Panacea 2.0.3?', 'it') == (
        'Scaricare e verificare Panacea 2.0.3?')
    text = translate('2 files · 1.5 MB freed · 0 skipped · 0 errors', 'it')
    assert text == '2 file · 1.5 MB liberati · 0 ignorati · 0 errori'
    assert translate('Running · Guided Maintenance', 'it') == (
        'In esecuzione · Manutenzione guidata')


@pytest.mark.parametrize(('source', 'expected'), [
    ('Running · Guided Maintenance', 'In esecuzione · Manutenzione guidata'),
    ('Partial · 3/10 steps finished', 'Parziale · 3/10 passaggi terminati'),
    ('Update failed: Executable SHA-256 does not match the release.',
     "Aggiornamento non riuscito: Lo SHA-256 dell'eseguibile non corrisponde a quello della release."),
    ('Download and verify Panacea 2.0.3?\nThe app stays open if verification or installation fails.',
     "Scaricare e verificare Panacea 2.0.3?\nL'app resterà aperta se la verifica o l'installazione non riesce."),
    ('Recycle bin operation returned code 3.', 'Svuotamento del Cestino terminato con codice 3.'),
    ('Battery report saved to C:\\Temp\\battery_report.html',
     'Report della batteria salvato in C:\\Temp\\battery_report.html'),
    ('System Restore state could not be verified. Check protection and administrator access.',
     'Impossibile verificare lo stato di Ripristino configurazione di sistema. '
     'Controlla Protezione sistema e i permessi di amministratore.'),
])
def test_system_operations_and_updater_errors_keep_information_in_italian(source, expected):
    assert translate(source, 'it') == expected
    assert translate(source, 'en') == source


def test_operation_prefixes_localize_after_specific_result_patterns():
    assert translate('Result: Restart required.', 'it') == 'Risultato: Riavvio necessario.'
    assert translate('Guided Maintenance: Restart required.', 'it') == (
        'Manutenzione guidata: Riavvio necessario.')
    assert translate('Quick cleanup: completed', 'it') == 'Pulizia rapida: completato'


def test_expandable_output_labels_translate_the_visible_prefix():
    assert translate('+ Cleanup details', 'it') == '+ Dettagli pulizia'
    assert translate('− Command output', 'it') == '− Output dei comandi'
    assert translate('+ Cleanup details', 'en') == '+ Cleanup details'

"""Translate safety-critical Qt confirmation warnings without altering backend actions.

If a backend warning changes, preserve the original rather than showing a
potentially outdated translation. The confirmation nonce is never localized.
"""
from __future__ import annotations

import re

from qt_app.catalog import ENTRIES
from qt_app.maintenance import OPEN_ACTIONS, TURBO, WARNINGS


_DEFAULT_EN = "This changes Windows settings. Save work; the operation may take time or require a restart."
_OPEN_EN = "Open a native Windows utility. Changes there require separate Windows interaction."
_TURBO_EN = (
    "Change Windows power, visual or service state. Original values are saved "
    "and restoration may fail if Windows policies intervene."
)
_DEFAULT_IT = "Questa operazione modifica Windows. Salva il lavoro: potrebbe richiedere tempo o un riavvio."
_OPEN_IT = "Apre uno strumento di Windows. Eventuali modifiche successive sono gestite in Windows."
_TURBO_IT = (
    "Modifica alimentazione, effetti grafici o servizi. Le impostazioni originali "
    "sono salvate, ma le policy di Windows potrebbero impedirne il ripristino."
)
_WARNINGS_IT = {
    "temp_clean": (
        "Elimina definitivamente i file temporanei idonei. I file bloccati o protetti "
        "vengono ignorati. L'operazione è irreversibile."
    ),
    "browser_clean": (
        "Elimina definitivamente le cache dei browser. Chiudi i browser prima di "
        "procedere: l'eliminazione è irreversibile."
    ),
    "recycle_empty": (
        "Svuota definitivamente l'intero Cestino, non solo alcuni file. "
        "L'eliminazione è irreversibile."
    ),
    "quick_cleanup": (
        "Elimina definitivamente i file temporanei e tutto il Cestino; avvia DISM per "
        "la pulizia dei componenti Windows, poi apre Pulizia disco per una selezione "
        "manuale. Le eliminazioni sono irreversibili."
    ),
    "resurrection": (
        "Dieci passaggi: prima un punto di ripristino nuovo e verificato, poi "
        "eliminazione irreversibile di cache browser, temporanei e Cestino, "
        "ripristino rete e controlli di Windows. Salva il lavoro. "
        "L'annullamento viene applicato solo fra i passaggi."
    ),
    "winsock_reset": (
        "Il ripristino della rete può interrompere le connessioni e richiedere "
        "un riavvio di Windows."
    ),
    "component_cleanup": (
        "Rimuove tramite DISM i componenti Windows sostituiti. "
        "Potrebbe essere necessario un riavvio."
    ),
}


def confirmation_text(action: str, prepared: dict, language: str) -> tuple[str, str]:
    """Return presentation text only; preserve any unrecognized backend warning."""
    title, raw = prepared["title"], prepared["details"]
    if language != "it":
        return title, raw
    if action in OPEN_ACTIONS:
        expected, translated = _OPEN_EN, _OPEN_IT
    elif action in TURBO:
        expected, translated = _TURBO_EN, _TURBO_IT
    else:
        expected = WARNINGS.get(action, _DEFAULT_EN)
        translated = _WARNINGS_IT.get(action, _DEFAULT_IT)
    if raw == expected:
        suffix = ""
    elif raw.startswith(expected):
        suffix = raw[len(expected):]
        match = re.fullmatch(r"\nSelected drive: ([A-Z]:)", suffix)
        if match is None:
            return title, raw
        suffix = "\nUnità selezionata: " + match.group(1)
    else:
        return title, raw
    return ENTRIES.get(action, (title,))[0], translated + suffix

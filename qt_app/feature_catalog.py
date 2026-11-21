"""Bilingual confirmation labels shared by the optional 2.2 features and shell."""
import unicodedata

ACTIONS = {
    "startup_enable": ("Abilita all'avvio", "Enable at sign-in"),
    "startup_disable": ("Disabilita all'avvio", "Disable at sign-in"),
    "deep_cleanup": ("Pulizia approfondita", "Deep cleanup"),
}
CATEGORIES = {
    "wer_reports": ("Segnalazioni errori Windows", "Windows error reports"),
    "thumbnail_cache": ("Cache miniature e icone", "Thumbnail and icon caches"),
    "shader_cache": ("Cache shader DirectX", "DirectX shader cache"),
    "delivery_optimization": ("Ottimizzazione recapito", "Delivery Optimization"),
    "crash_dumps": ("Dump di arresto anomalo", "Crash dumps"),
    "panacea_leftovers": ("Download Panacea scaduti", "Stale Panacea downloads"),
}


def action_label(action, language):
    return ACTIONS[action][language != "it"]


def selection_label(action, selection, language):
    if action == "deep_cleanup":
        selection = ", ".join(CATEGORIES[key][language != "it"] for key in selection.split(", "))
    else:
        selection = "".join(c if not unicodedata.category(c).startswith("C") else " " for c in selection)
    return ("Selezione: " if language == "it" else "Selection: ") + selection

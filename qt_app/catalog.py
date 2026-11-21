"""Section and palette data. Action identifiers belong to the maintenance service."""
from qt_app.i18n import messages


SECTIONS = ("home", "cleanup", "startup", "repair", "performance", "guided", "history", "updates", "settings")

SECTION_ACTIONS = {
    "home": ("quick_cleanup", "windows_update", "windows_optional", "restore_point"),
    "cleanup": ("quick_cleanup", "temp_clean", "browser_clean", "recycle_empty", "component_cleanup", "open_cleanmgr"),
    "startup": ("startup_settings", "apps_settings", "appwiz"),
    "repair": ("sfc", "dism_check", "dism_restore", "chkdsk", "dns_flush", "winsock_reset",
               "restore_point", "battery_report"),
    "performance": ("turbo_on", "turbo_off", "power_on", "power_off", "visual_on", "visual_off",
                    "sysmain_on", "sysmain_off", "wsearch_on", "wsearch_off", "spooler_on", "spooler_off",
                    "drive_optimize", "open_defrag"),
    "guided": ("resurrection",),
    "history": (),
    "updates": (),
    "settings": (),
}

# The safety-critical confirmation presenter consumes this established layout.
ENTRIES = {
    action: tuple(messages(lang)[f"action.{action}.{key}"]
                  for key in ("title", "description") for lang in ("it", "en"))
    for actions in SECTION_ACTIONS.values() for action in actions
}


def palette_entries():
    """Labels and search terms come from both catalogs, regardless of UI language."""
    entries = []
    for section in SECTIONS:
        key = f"nav.{section}"
        titles = [messages(lang)[key] for lang in ("it", "en")]
        names = " ".join(titles)
        entries.append({"section": section, "action": "", "titleKey": key, "descriptionKey": "",
                        "titles": titles, "keywords": f"{section} {names}"})
        for action in SECTION_ACTIONS[section]:
            if section == "home" and action in ("quick_cleanup", "restore_point"):
                continue  # These shortcuts have dedicated cleanup and repair pages.
            entries.append({"section": section, "action": action, "titleKey": f"action.{action}.title",
                            "descriptionKey": f"action.{action}.description",
                            "titles": list(ENTRIES[action][:2]),
                            "keywords": " ".join((action, action.replace("_", " "), names, *ENTRIES[action]))})
    return entries

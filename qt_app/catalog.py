"""Localized Qt Quick action catalog. Data only, never shell commands."""
from qt_app.maintenance import ACTIONS

ENTRIES = {
  "cpu": [
    "Processore",
    "Processor",
    "Utilizzo corrente CPU",
    "Current CPU use"
  ],
  "ram": [
    "Memoria",
    "Memory",
    "RAM utilizzata",
    "Memory usage"
  ],
  "disk": [
    "Disco",
    "Disk",
    "Volume di sistema",
    "System volume"
  ],
  "temp_clean": [
    "File temporanei",
    "Temporary files",
    "Pulizia diretta irreversibile",
    "Irreversible direct cleanup"
  ],
  "browser_clean": [
    "Cache browser",
    "Browser caches",
    "Chrome, Edge e Firefox",
    "Chrome, Edge and Firefox"
  ],
  "recycle_empty": [
    "Cestino",
    "Recycle Bin",
    "Svuotamento completo",
    "Empty entire Recycle Bin"
  ],
  "quick_cleanup": [
    "Pulizia rapida",
    "Quick cleanup",
    "Temp, Cestino, DISM, utilità manuale",
    "Temp, Bin, DISM, manual utility"
  ],
  "component_cleanup": [
    "Archivio componenti",
    "Component store",
    "DISM StartComponentCleanup",
    "DISM StartComponentCleanup"
  ],
  "open_cleanmgr": [
    "Pulizia disco",
    "Disk Cleanup",
    "Strumento nativo Windows",
    "Native Windows utility"
  ],
  "apps_settings": [
    "Gestione applicazioni",
    "Manage apps",
    "Impostazioni Windows",
    "Windows Settings"
  ],
  "appwiz": [
    "Programmi classici",
    "Classic programs",
    "Pannello di controllo",
    "Control Panel"
  ],
  "sfc": [
    "SFC",
    "SFC",
    "Controllo file di sistema",
    "System file check"
  ],
  "dism_check": [
    "DISM CheckHealth",
    "DISM CheckHealth",
    "Controllo integrità immagine",
    "Image health check"
  ],
  "dism_restore": [
    "DISM RestoreHealth",
    "DISM RestoreHealth",
    "Riparazione Windows",
    "Windows image repair"
  ],
  "dns_flush": [
    "DNS",
    "DNS",
    "Svuota cache DNS",
    "Flush DNS cache"
  ],
  "winsock_reset": [
    "Winsock",
    "Winsock",
    "Ripristino rete",
    "Reset network stack"
  ],
  "drive_optimize": [
    "Ottimizza unità",
    "Optimize drive",
    "Ottimizza il disco selezionato",
    "Optimize selected drive"
  ],
  "chkdsk": [
    "CHKDSK",
    "CHKDSK",
    "Scansione volume selezionato",
    "Scan selected drive"
  ],
  "open_defrag": [
    "Gestione dischi",
    "Drive manager",
    "Ottimizzazione nativa Windows",
    "Native Windows optimization"
  ],
  "restore_point": [
    "Punto di ripristino",
    "Restore point",
    "Crea e verifica",
    "Create and verify"
  ],
  "battery_report": [
    "Rapporto batteria",
    "Battery report",
    "Salva un rapporto HTML",
    "Save HTML report"
  ],
  "windows_update": [
    "Windows Update",
    "Windows Update",
    "Apri aggiornamenti Windows",
    "Open Windows updates"
  ],
  "windows_optional": [
    "Aggiornamenti facoltativi",
    "Optional updates",
    "Gestione aggiornamenti",
    "Manage optional updates"
  ],
  "turbo_on": [
    "Turbo ON",
    "Enable Turbo",
    "Attiva preset completo",
    "Enable full performance preset"
  ],
  "turbo_off": [
    "Turbo OFF",
    "Restore Turbo",
    "Ripristina originali",
    "Restore original settings"
  ],
  "power_on": [
    "Energia ON",
    "High performance",
    "Attiva il piano elevato",
    "Enable high-performance plan"
  ],
  "power_off": [
    "Energia OFF",
    "Restore power",
    "Ripristina piano originale",
    "Restore original power plan"
  ],
  "visual_on": [
    "Effetti Turbo ON",
    "Disable visual effects",
    "Riduci effetti visivi",
    "Reduce visual effects"
  ],
  "visual_off": [
    "Effetti Turbo OFF",
    "Restore visual effects",
    "Ripristina effetti",
    "Restore visual effects"
  ],
  "sysmain_on": [
    "SysMain OFF",
    "Stop SysMain",
    "Interrompi servizio",
    "Stop service"
  ],
  "sysmain_off": [
    "Ripristina SysMain",
    "Restore SysMain",
    "Ripristina stato iniziale",
    "Restore original state"
  ],
  "wsearch_on": [
    "WSearch OFF",
    "Stop Windows Search",
    "Ferma indicizzazione",
    "Stop indexing"
  ],
  "wsearch_off": [
    "Ripristina WSearch",
    "Restore Windows Search",
    "Ripristina indicizzazione",
    "Restore indexing"
  ],
  "spooler_on": [
    "Spooler OFF",
    "Stop Spooler",
    "Interrompi servizio stampa",
    "Stop print service"
  ],
  "spooler_off": [
    "Ripristina Spooler",
    "Restore Spooler",
    "Ripristina servizio",
    "Restore print service"
  ],
  "startup_settings": [
    "App all'avvio",
    "Startup apps",
    "Impostazioni avvio",
    "Windows startup settings"
  ],
  "resurrection": [
    "Resurrection",
    "Resurrection",
    "Manutenzione completa in dieci fasi",
    "Full ten-step maintenance"
  ]
}
GROUPS = [
  [
    "cpu",
    "ram",
    "disk"
  ],
  [
    "temp_clean",
    "browser_clean",
    "recycle_empty",
    "quick_cleanup",
    "component_cleanup",
    "open_cleanmgr",
    "apps_settings",
    "appwiz"
  ],
  [
    "sfc",
    "dism_check",
    "dism_restore",
    "dns_flush",
    "winsock_reset",
    "drive_optimize",
    "chkdsk",
    "open_defrag",
    "restore_point",
    "battery_report",
    "windows_update",
    "windows_optional"
  ],
  [
    "turbo_on",
    "turbo_off",
    "power_on",
    "power_off",
    "visual_on",
    "visual_off",
    "sysmain_on",
    "sysmain_off",
    "wsearch_on",
    "wsearch_off",
    "spooler_on",
    "spooler_off",
    "startup_settings"
  ],
  [
    "resurrection"
  ]
]
METRICS = frozenset({"cpu", "ram", "disk"})


def cards(language="it"):
    italian = language == "it"
    pages = []
    for group in GROUPS:
        page = []
        for key in group:
            it_title, en_title, it_sub, en_sub = ENTRIES[key]
            metric = key if key in METRICS else ""
            page.append({
                "title": it_title if italian else en_title,
                "subtitle": it_sub if italian else en_sub,
                "note": ("Richiede conferma; controlla i risultati nel log." if italian
                         else "Requires confirmation; review results in the log.") if not metric else
                        ("Monitoraggio live." if italian else "Live monitoring."),
                "badge": "LIVE" if metric else "ACTION",
                "metric": metric,
                "value": "" if metric else ("Conferma" if italian else "Confirm"),
                "action": key if key in ACTIONS else "",
            })
        pages.append(page)
    return pages

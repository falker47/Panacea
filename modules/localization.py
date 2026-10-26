"""Interface translations and locale selection for installed and portable Panacea.

The installer writes its Inno Setup language beside the protected executable.
Portable/source builds instead use the Windows user UI language. Translation is
presentation-only: operation identifiers, commands and file paths stay unchanged.
"""
import configparser
import locale
import os
from pathlib import Path
import re
import sys

LOCALE_FILE = "panacea-language.ini"

# English copy remains canonical in the UI; only visible presentation is mapped.
_PAIRS = """
System maintenance => Manutenzione del sistema
Overview => Panoramica
Space & Cleanup => Spazio e pulizia
Diagnostics & Repair => Diagnostica e riparazione
Performance & Startup => Prestazioni e avvio
Guided Maintenance => Manutenzione guidata
Panacea is already up to date. => Panacea è già aggiornato all'ultima versione.
Checking Panacea updates… => Verifica aggiornamenti Panacea…
Check updates => Cerca aggiornamenti
Retry check => Riprova controllo
Install update => Installa aggiornamento
Download / install => Scarica / installa
Release notes => Note di rilascio
Defer => Rimanda
Update deferred => Aggiornamento rimandato
Use Check updates when ready => Usa Cerca aggiornamenti quando vuoi
Ready => Pronto
Ready · No operation running => Pronto · Nessuna operazione in corso
Ready · No cleanup started => Pronto · Pulizia non avviata
Ready · No steps run => Pronto · Nessun passaggio eseguito
Analysis optional · No files deleted => Analisi facoltativa · Nessun file eliminato
Loading Windows details… => Caricamento dettagli di Windows…
Uptime: — => Attività: —
Power: — => Alimentazione: —
Windows Update => Windows Update
Checking… => Verifica in corso…
Check failed => Verifica non riuscita
View => Apri
CPU => CPU
Memory (RAM) => Memoria (RAM)
System drive => Unità di sistema
Loading processor… => Caricamento processore…
RAM: — => RAM: —
Loading memory details… => Caricamento dettagli memoria…
Storage: — => Archiviazione: —
Checking space… => Verifica dello spazio…
Loading disk details… => Caricamento dettagli unità…
Temporary files => File temporanei
Restore point => Punto di ripristino
Analyze => Analizza
Create => Crea
Save Windows state · confirmation required => Salva lo stato di Windows · conferma richiesta
Activity details => Dettagli attività
Cleanup => Pulizia
One confirmed cleanup or individual tools. Protected files remain untouched. => Pulizia confermata unica o strumenti singoli. I file protetti non vengono toccati.
Quick cleanup => Pulizia rapida
Temporary files · Recycle Bin · Windows component store => File temporanei · Cestino · Componenti Windows
Then Windows Disk Cleanup opens for manual selection. => Poi si apre Pulizia disco di Windows per la selezione manuale.
Run quick cleanup => Avvia pulizia rapida
Show individual tools => Mostra strumenti singoli
Hide individual tools => Nascondi strumenti singoli
Delete temporary files => Elimina file temporanei
Permanent deletion after confirmation; no analysis required => Eliminazione definitiva dopo conferma; analisi non necessaria
Clean now => Pulisci ora
Recycle Bin => Cestino
Permanently empty all items · confirmation required => Svuota definitivamente tutti gli elementi · conferma richiesta
Empty bin => Svuota cestino
Component store => Componenti Windows
Windows removes superseded components. => Windows rimuove i componenti sostituiti.
Clean store => Pulisci componenti
Windows Disk Cleanup => Pulizia disco di Windows
Choose categories in the Windows utility. => Scegli le categorie nell'utilità Windows.
Open utility => Apri utilità
Cleanup details => Dettagli pulizia
Drive optimization => Ottimizzazione unità
Select a drive; Windows chooses the correct optimization method. => Seleziona un'unità; Windows sceglie il metodo di ottimizzazione.
Loading… => Caricamento…
No drives => Nessuna unità
Refresh => Aggiorna
Reading local drives… => Lettura unità locali…
Optimize selected drive => Ottimizza unità selezionata
Windows chooses TRIM or defragmentation. May take several minutes. => Windows sceglie TRIM o deframmentazione. Può richiedere diversi minuti.
Optimize => Ottimizza
Windows drive optimization => Ottimizzazione unità Windows
View schedules and drive health in Windows. => Controlla programmazione e stato unità in Windows.
Optimization output => Risultato ottimizzazione
Repair tools => Strumenti di riparazione
Check integrity or repair Windows and network issues. => Verifica l'integrità o ripara problemi di Windows e della rete.
WINDOWS INTEGRITY => INTEGRITÀ WINDOWS
NETWORK => RETE
System file scan => Analisi file di sistema
Verify and repair protected files. => Verifica e ripara i file protetti.
SFC scan => Analisi SFC
Scan => Analizza
Image health => Integrità immagine
Check the component image for recorded corruption. => Controlla i danni registrati nell'immagine di sistema.
DISM health check => Controllo integrità DISM
Check => Controlla
Repair image => Ripara immagine
Repair corruption; may use Windows Update. => Ripara i danni; può usare Windows Update.
DISM repair => Riparazione DISM
Repair => Ripara
Flush DNS => Svuota DNS
Clear cached DNS records. => Cancella i record DNS memorizzati.
DNS flush => Svuotamento DNS
Flush => Svuota
Reset Winsock => Reimposta Winsock
May interrupt connections and require a restart. => Può interrompere le connessioni e richiedere un riavvio.
Network reset => Ripristino rete
Reset => Ripristina
Run => Esegui
Battery report => Report batteria
Command output => Output comandi
Installed apps => App installate
Review installed software using Windows settings. => Gestisci il software installato tramite le impostazioni di Windows.
Review storage use, repair or uninstall apps. => Controlla lo spazio, ripara o disinstalla le app.
Apps settings => Impostazioni app
Classic programs => Programmi classici
Windows handles app changes. Return here when finished. => Windows gestisce le modifiche alle app. Torna qui al termine.
Startup apps => App all'avvio
Choose which apps launch when you sign in. => Scegli quali app avviare all'accesso.
Review startup impact and disable unnecessary auto-start entries. => Controlla l'impatto all'avvio e disattiva le app non necessarie.
Startup settings => Impostazioni di avvio
Windows manages startup changes. Return here when finished. => Windows gestisce le modifiche all'avvio. Torna qui al termine.
Disable unnecessary apps at sign-in. => Disattiva gli avvii automatici non necessari.
Manage or uninstall programs in Windows. => Gestisci o disinstalla i programmi in Windows.
Windows selects TRIM or defragmentation. => Windows sceglie TRIM o deframmentazione.
Open Windows drive optimizer => Apri ottimizzazione unità Windows.
Original settings are saved for restoration. => Le impostazioni originali vengono salvate per il ripristino.
Adjust Windows animations. => Regola le animazioni di Windows.
Stops app preloading. => Ferma il precaricamento delle app.
Stops background indexing. => Ferma l'indicizzazione in background.
Saved settings unavailable · Refresh state => Impostazioni salvate non disponibili · Aggiorna stato
Performance settings => Impostazioni prestazioni
Original settings are saved before changes and restored when turned off. => Le impostazioni originali vengono salvate e ripristinate alla disattivazione.
All settings => Tutte le impostazioni
Reading saved originals… => Lettura impostazioni salvate…
Restore saved settings => Ripristina impostazioni salvate
Refresh state => Aggiorna stato
High performance => Prestazioni elevate
More power use, heat and battery drain. => Aumenta consumi, calore e uso della batteria.
Visual effects preset => Effetti visivi
Save the Windows performance preference. => Salva le preferenze di prestazioni Windows.
Pause SysMain => Sospendi SysMain
Pause application preloading. => Sospendi il precaricamento delle applicazioni.
Pause Windows Search => Sospendi Windows Search
Pause background indexing. => Sospendi l'indicizzazione in background.
Pause Print Spooler => Sospendi spooler di stampa
Printing is unavailable while active. => La stampa non è disponibile durante la sospensione.
Unknown => Sconosciuto
Active => Attivo
Inactive => Inattivo
Resurrection => Manutenzione guidata
SEQUENCE STATUS => STATO DELLA SEQUENZA
Before you start => Prima di iniziare
Maintenance steps => Passaggi di manutenzione
Select Details for step information and results. => Seleziona Dettagli per informazioni e risultati del passaggio.
Details => Dettagli
10 steps · Verified restore point required => 10 passaggi · Punto di ripristino verificato obbligatorio
Start sequence => Avvia sequenza
Cancel after step => Annulla dopo il passaggio
Not started => Non avviato
Running… => In esecuzione…
Completed => Completato
Failed => Non riuscito
Failed / partial => Non riuscito / parziale
Not run => Non eseguito
pending => in attesa
running => in esecuzione
completed => completato
partial => parziale
cancelled => annullato
failed => non riuscito
interrupted => interrotto
Full sequence output => Output sequenza completa
Browser caches => Cache dei browser
DNS cache => Cache DNS
Optimize drive => Ottimizza unità
Disk scan => Analisi disco
Disk health scan => Verifica disco
Windows image health => Integrità immagine Windows
System files => File di sistema
Available => Disponibile
Unavailable => Non disponibile
Local => Locale
No available local drive => Nessuna unità locale disponibile
Cannot read drive => Impossibile leggere l'unità
Capacity unavailable => Capacità non disponibile
Space available => Spazio disponibile
Low free space => Spazio libero insufficiente
Memory unavailable => Memoria non disponibile
Drive information unavailable => Informazioni unità non disponibili
Processor details unavailable => Dettagli processore non disponibili
Memory details unavailable => Dettagli memoria non disponibili
Disk details unavailable => Dettagli disco non disponibili
Command state unknown => Stato del comando sconosciuto
Operation in progress => Operazione in corso
Wait for the current operation to finish. => Attendi il termine dell'operazione corrente.
Failed · See sequence output => Errore · Consulta l'output della sequenza
Metrics unavailable => Metriche non disponibili
Analysis => Analisi
No files deleted => Nessun file eliminato
Scanning temporary files… No files deleted => Analisi file temporanei… Nessun file eliminato
Not scanned yet => Non ancora analizzato
Analysis completed => Analisi completata
Analysis failed => Analisi non riuscita
Analysis partial => Analisi parziale
Analysis interrupted => Analisi interrotta
Cleanup completed => Pulizia completata
Cleanup failed => Pulizia non riuscita
Cleanup partial => Pulizia parziale
Cleanup interrupted => Pulizia interrotta
files deleted => file eliminati
files => file
skipped => ignorati
errors => errori
candidates => candidati
recoverable => recuperabili
freed => liberati
about => circa
Temporary file analysis => Analisi file temporanei
Temporary file cleanup => Pulizia file temporanei
Empty Recycle Bin => Svuota cestino
Disk Cleanup => Pulizia disco
Command completion unknown => Completamento del comando sconosciuto
Sequence stopped => Sequenza interrotta
starting => in avvio
Completed. => Completato.
Failed. => Non riuscito.
See command output. => Consulta l'output dei comandi.
See drive output. => Consulta l'output dell'unità.
Restart required. => Riavvio necessario.
See command output for details. => Consulta l'output dei comandi per i dettagli.
See optimization output for details. => Consulta l'output dell'ottimizzazione per i dettagli.
Network connections may be interrupted and a restart may be needed. => La connessione potrebbe interrompersi e potrebbe essere necessario riavviare.
The operation can take several minutes. Save your work first. => L'operazione può richiedere diversi minuti. Salva prima il lavoro.
Clean temporary files now => Pulisci file temporanei adesso
Confirm quick cleanup => Conferma pulizia rapida
Select a drive => Seleziona un'unità
Choose a valid drive letter. => Scegli una lettera di unità valida.
Create restore point => Crea punto di ripristino
Confirm Resurrection => Conferma manutenzione guidata
Confirm Guided Maintenance => Conferma manutenzione guidata
Maintenance running… => Manutenzione in corso…
Cancel after current step => Annulla dopo il passaggio corrente
Cancellation requested… => Annullamento richiesto…
Starting · Verifying restore point => Avvio · Verifica punto di ripristino
Starting · 0/3 automatic steps attempted => Avvio · 0/3 passaggi automatici tentati
opened => aperto
Opened => Aperto
Ready to retry => Pronto per riprovare
Restart required => Riavvio necessario
Optional updates => Aggiornamenti facoltativi
Update => Aggiornamento
Update failed => Aggiornamento non riuscito
Update check failed => Controllo aggiornamenti non riuscito
Verified · Preparing installation… => Verificato · Preparazione installazione…
Downloading and verifying… => Download e verifica in corso…
Verifying downloaded executable… => Verifica eseguibile scaricato…
Retry install => Riprova installazione
Finish the current operation before updating. => Termina l'operazione corrente prima di aggiornare.
Install verified update => Installa aggiornamento verificato
Update installation in progress => Installazione aggiornamento in corso
Wait for installation to finish before closing Panacea. => Attendi il termine dell'installazione prima di chiudere Panacea.
Report saved => Report salvato
Panacea Manual Point => Punto manuale Panacea
Component store cleanup => Pulizia componenti Windows
Restore Turbo settings => Ripristino impostazioni Turbo
Turbo settings => Impostazioni Turbo
Turbo setting => Impostazione Turbo
No saved changes => Nessuna modifica salvata
Saved originals unavailable => Impostazioni salvate non disponibili
retry Refresh state => riprova Aggiorna stato
available for restoration => disponibili per il ripristino
switches show the current Windows state => gli interruttori mostrano lo stato Windows attuale
Automatic steps attempted => Passaggi automatici tentati
No cleanup started => Pulizia non avviata
No further sequence steps will start => Non verranno avviati altri passaggi
""".strip()

ITALIAN = dict(line.split(" => ", 1) for line in _PAIRS.splitlines())

WARNINGS = {
    "Permanent deletion: browser caches, temporary files and Recycle Bin items; restore points cannot recover them.\nNetwork reset can interrupt connections or require restart. Save work; cancellation stops between steps.":
        "Eliminazione definitiva di cache dei browser, file temporanei e Cestino: i punti di ripristino non recuperano questi dati.\nIl ripristino della rete può interrompere le connessioni o richiedere un riavvio. Salva il lavoro; l'annullamento avviene tra i passaggi.",
    "Permanent deletion: browser caches, temp files and all Recycle Bin items. Restore points cannot recover deleted files.\nNetwork reset may disconnect you or require a restart. Save work. Cancel stops between commands.":
        "Eliminazione definitiva di cache browser, file temporanei e tutto il Cestino. I punti di ripristino non recuperano i file eliminati.\nIl ripristino rete può disconnetterti o richiedere un riavvio. Salva il lavoro. L'annullamento avviene tra i comandi.",
    "Safety · Verify a new Windows restore point. Deleted files are NOT recoverable.":
        "Sicurezza · Verifica un nuovo punto di ripristino Windows. I file eliminati NON sono recuperabili.",
    "Cleanup · Remove temporary web browser cache data.":
        "Pulizia · Rimuove i dati di cache temporanei dei browser.",
    "Cleanup · Remove eligible temporary files; protected items are skipped.":
        "Pulizia · Rimuove i file temporanei idonei; gli elementi protetti vengono ignorati.",
    "Cleanup · Permanently delete all items in the Recycle Bin.":
        "Pulizia · Elimina definitivamente tutti gli elementi del Cestino.",
    "Network · Refresh locally cached domain-name lookups.":
        "Rete · Aggiorna le risoluzioni DNS memorizzate.",
    "Network · Reset Winsock; a restart may be needed.":
        "Rete · Reimposta Winsock; potrebbe servire un riavvio.",
    "Disk · Let Windows choose TRIM or defragmentation.":
        "Disco · Lascia scegliere a Windows tra TRIM e deframmentazione.",
    "Disk · Scan the file system for errors (online CHKDSK).":
        "Disco · Cerca errori nel file system (CHKDSK online).",
    "Repair · Check recorded corruption in the Windows component image.":
        "Riparazione · Controlla i danni registrati nell'immagine Windows.",
    "Repair · Scan and repair protected Windows files (SFC).":
        "Riparazione · Analizza e ripara i file Windows protetti (SFC).",
    "Permanently delete eligible files in validated temporary folders?\n\nNo analysis is required. Files are checked as they are deleted; locked and protected items are skipped. Results may differ from an earlier analysis.\n\nDeletion cannot be undone through the Recycle Bin.":
        "Eliminare definitivamente i file idonei nelle cartelle temporanee verificate?\n\nNon serve alcuna analisi preliminare. I file sono verificati durante l'eliminazione; quelli bloccati o protetti sono ignorati. I risultati possono differire da un'analisi precedente.\n\nNon è possibile annullare l'eliminazione tramite il Cestino.",
    "Permanently delete every item in the Recycle Bin?\nThese items cannot be recovered through the Recycle Bin.":
        "Eliminare definitivamente tutti gli elementi del Cestino?\nNon saranno recuperabili tramite il Cestino.",
    "Run the following cleanup operations in sequence?\n\n1. Permanently delete eligible files in validated temporary folders.\n2. Permanently empty the ENTIRE Recycle Bin.\n3. Remove superseded Windows components using DISM.\n4. OPEN Windows Disk Cleanup for your manual selection and confirmation.\n\nDeletion is irreversible, including through Windows restore points. Some files may be skipped; DISM may take time or require a restart. Save your work first.\n\nContinue?":
        "Eseguire queste operazioni in sequenza?\n\n1. Eliminare definitivamente i file idonei nelle cartelle temporanee verificate.\n2. Svuotare definitivamente TUTTO il Cestino.\n3. Rimuovere i componenti Windows sostituiti tramite DISM.\n4. APRIRE Pulizia disco Windows per selezione e conferma manuale.\n\nL'eliminazione è irreversibile anche tramite punti di ripristino. Alcuni file potrebbero essere ignorati; DISM può richiedere tempo o un riavvio. Salva prima il lavoro.\n\nContinuare?",
    "Create and verify a new Windows restore point?\nSystem protection must already be enabled. This may take a minute.":
        "Creare e verificare un nuovo punto di ripristino Windows?\nLa protezione del sistema deve essere già attiva. Può richiedere un minuto.",
    "Run all 10 maintenance steps?\n\nAfter verifying a new restore point, Panacea permanently deletes browser caches, temporary files and ALL Recycle Bin items, then resets network settings and scans the system.\n\nDeletion cannot be undone through the Recycle Bin. Network connections may be interrupted; a restart may be needed. Save your work first.":
        "Eseguire tutti i 10 passaggi di manutenzione?\n\nDopo aver verificato un nuovo punto di ripristino, Panacea elimina definitivamente cache dei browser, file temporanei e TUTTO il Cestino; poi reimposta la rete e analizza il sistema.\n\nL'eliminazione non si può annullare dal Cestino. La rete può disconnettersi ed essere necessario riavviare. Salva prima il lavoro.",
}

PATTERNS = [
    (r"^Panacea ([\w.]+) is up to date$", r"Panacea \1 è aggiornato"),
    (r"^Panacea ([\w.]+) available$", r"Panacea \1 disponibile"),
    (r"^You are using Panacea ([\w.+-]+)\. Update to version ([\w.+-]+) is available\.$",
     r"Stai usando Panacea \1. È disponibile l'aggiornamento alla versione \2."),
    (r"^Uptime: (.+)$", r"Attività: \1"),
    (r"^Power: (.+)$", r"Alimentazione: \1"),
    (r"^Battery: (.+)$", r"Batteria: \1"),
    (r"^(.+) GB used / (.+) GB$", r"\1 GB usati / \2 GB"),
    (r"^(.+) GB free / (.+) GB$", r"\1 GB liberi / \2 GB"),
    (r"^(.+)% used$", r"\1% utilizzato"),
    (r"^(.+) original settings saved$", r"\1 impostazioni originali salvate"),
    (r"^(\d+) / (\d+) steps$", r"\1 / \2 passaggi"),
    (r"^(.+) steps finished$", r"\1 passaggi terminati"),
    (r"^(.+) finished$", r"\1 completati"),
    (r"^(.+) files deleted$", r"\1 file eliminati"),
    (r"^(.+) files$", r"\1 file"),
    (r"^(.+) skipped$", r"\1 ignorati"),
    (r"^(.+) errors$", r"\1 errori"),
    (r"^(.+) candidates$", r"\1 candidati"),
    (r"^about (.+) recoverable$", r"circa \1 recuperabili"),
    (r"^(.+) freed$", r"\1 liberati"),
    (r"^(.+) automatic steps attempted$", r"\1 passaggi automatici tentati"),
    (r"^(.+) automatic steps completed$", r"\1 passaggi automatici completati"),
    (r"^Run (.+)\?$", r"Eseguire \1?"),
    (r"^Run Windows optimization on (.+)\?$", r"Eseguire l'ottimizzazione Windows su \1?"),
    (r"^Downloading · (.+)%$", r"Download · \1%"),
    (r"^(.+) available for restoration$", r"\1 disponibili per il ripristino"),
    (r"^Update check failed: (.+)$", r"Controllo aggiornamenti non riuscito: \1"),
    (r"^Update failed: (.+)$", r"Aggiornamento non riuscito: \1"),
    (r"^Drive query failed: (.+)$", r"Ricerca unità non riuscita: \1"),
    (r"^Drive information unavailable: (.+)$", r"Informazioni unità non disponibili: \1"),
    (r"^Metrics unavailable: (.+)$", r"Metriche non disponibili: \1"),
    (r"^(.+) unavailable: (.+)$", r"\1 non disponibile: \2"),
    (r"^Opened (.+)$", r"Aperto \1"),
    (r"^Failed · (.+)$", r"Errore · \1"),
    (r"^Running · (.+)$", r"In esecuzione · \1"),
    (r"^Stopped · (.+)$", r"Interrotto · \1"),
    (r"^Completed · (.+)$", r"Completato · \1"),
    (r"^(.+) failed$", r"\1 non riuscito"),
    (r"^Result: (.+)$", r"Risultato: \1"),
]

def _normalize(language):
    value = str(language or "").casefold().strip().replace("-", "_")
    return "it" if value in ("it", "italian", "it_it") or value.startswith("it_") else "en"


def read_installed_language(executable):
    """Only inspect the exact sidecar path, never enumerate arbitrary directories."""
    if not executable:
        return None
    path = Path(executable).with_name(LOCALE_FILE)
    try:
        parser = configparser.ConfigParser(interpolation=None)
        with path.open("r", encoding="utf-8") as stream:
            parser.read_file(stream)
        value = parser.get("Panacea", "Language", fallback="").casefold()
        return _normalize(value) if value in ("english", "italian") else None
    except (OSError, ValueError, configparser.Error):
        return None


def resolve_language(*, executable=None, system_language=None, override=None):
    """Installed choice wins. Explicit override supports development and QA."""
    if executable is None and getattr(sys, "frozen", False):
        executable = sys.executable
    installed = read_installed_language(executable)
    if installed:
        return installed
    if override is None:
        override = os.getenv("PANACEA_LANGUAGE")
    if override:
        return _normalize(override)
    if system_language is None:
        try:
            import ctypes
            system_language = "it" if ctypes.windll.kernel32.GetUserDefaultUILanguage() == 0x0410 else None
        except (AttributeError, OSError):
            pass
    if system_language is None:
        system_language = locale.getlocale()[0] or "en"
    return _normalize(system_language)


def translate(text, language="en"):
    if not isinstance(text, str) or _normalize(language) != "it" or not text:
        return text
    if text in ITALIAN:
        return ITALIAN[text]
    if text in WARNINGS:
        return WARNINGS[text]
    if "\n" in text:
        return "\n".join(translate(line, "it") for line in text.split("\n"))
    if " · " in text:
        return " · ".join(translate(part, "it") for part in text.split(" · "))
    for pattern, replacement in PATTERNS:
        if re.fullmatch(pattern, text):
            return re.sub(pattern, replacement, text)
    return text

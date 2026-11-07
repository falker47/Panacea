# Panacea Qt — candidato QA, non una release

Interfaccia PySide6/Qt Quick basata sugli stessi backend Python della V2.
Il branch e la PR #7 restano separati da main.

## Operazioni collegate

- Dashboard: CPU, RAM e disco live; dati hardware.
- Cleanup & Apps: analisi temporanei in sola lettura; pulizia reale di temporanei e cache browser, Cestino, quick cleanup e DISM; collegamenti alle utilità Windows e gestione app.
- Tools & Disk: SFC, DISM, DNS, Winsock, CHKDSK, defrag con unità validata; punto di ripristino, rapporto batteria, Windows Update.
- Turbo & Startup: preset e controlli individuali con salvataggio/ripristino dello stato originale; app all'avvio gestite dalle impostazioni Windows.
- Resurrection: dieci fasi, punto di ripristino obbligatorio, progress e cancellazione fra fasi.

Le letture restano separate dalle mutazioni. Il controller manutenzione espone soltanto una allowlist, nonce di conferma monouso, verifica amministratore, blocco di concorrenza, MaintenanceGuard e segnalazione dei processi a completamento incerto. Non considera terminato un processo Windows soltanto perché l'interfaccia ha ricevuto una richiesta di cancellazione.

La UI presenta conferme esplicite per le operazioni irreversibili, risultati e log durante la navigazione, cinque destinazioni principali e testi IT/EN.

## Gate aperti

- Updater e installer Qt NON integrati: i meccanismi stabili presuppongono la propria identità binaria, verifica SHA-256, provenienza, ACL, rollback e readiness.
- Le funzioni sono cablate ma i test con fake e gli smoke della finestra non dimostrano un comportamento reale sicuro in Windows.
- Manca QA isolata di elevazione UAC, servizi, pulizia, ripristino, cancellazione, timeout, visual/accessibilità e misure di prestazioni a parità funzionale.
- Mai eseguire prove distruttive sul PC dell'utente per validare la build QA; mai fare merge né release finché non sono soddisfatti i gate.

## QA Windows

Dalla radice, usare l'ambiente del repository.
Installare requirements-dev.txt e qt_lab/requirements.txt, quindi eseguire la discovery unittest qt_app/tests.
Avviare qt_app/main.py con --smoke-test e --capture per uno screenshot senza manutenzione.

GitHub Actions pubblica soltanto un artefatto candidato standalone, uno SHA-256 del pacchetto e screenshot. Non è un aggiornamento automatico della V2 stabile.

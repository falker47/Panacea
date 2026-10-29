# Panacea Qt — migrazione in corso (NON una release)

Branch di sviluppo separato dal prototipo read-only e da \`main\`. La nuova UI PySide6/Qt Quick conserva il linguaggio visivo approvato e importa il **backend Python esistente** tramite un contratto esplicito. La release stabile CustomTkinter resta immutata.

## Perimetro dell'attuale milestone

**Collegati alla UI Qt:** CPU/RAM/disco live (già verificati nel lab), letture hardware, analisi temporanei *senza cancellazione*, inventario dischi, lettura Turbo e stato del blocco manutenzione. I nuovi comandi passano attraverso il modulo \`qt_app.services.ReadService\` e il dispatcher già utilizzato da Panacea, con worker separati.

**Non ancora migrati, quindi non attivabili:** pulizia effettiva, Cestino, DISM/SFC/CHKDSK, ottimizzazione dischi, restore points, Turbo scritture/ripristino, quick cleanup, Resurrection, installazione/update, UAC/installer. Le schede QML in queste aree sono dimostrative e marcate come tali. Non dichiarare parità funzionale.

## Contratti prima di attivare operazioni Windows

1. **Nessuna stringa comando arbitraria da QML:** utilizzare una mappa di operazioni consentite e validare lettere di unità, percorsi e argomenti nel backend.
2. **Una sola operazione di manutenzione per volta:** preservare lo stato busy fra worker, completamento sul thread principale, cancel fra passi e output persistente dopo navigazione.
3. **Conferma informata esplicita per ogni azione irreversibile**, privilegi verificati; read-only e pulsanti di modifica non devono condividere lo stesso contratto.
4. **Preservare \`MaintenanceGuard\`**, salvataggio di completamento sconosciuto e divieto di ulteriori operazioni anche dopo riavvio dell'app; il semplice timeout non prova che il processo sia terminato.
5. **Preservare i backend originali e i test di sicurezza**, senza refactoring non necessari e senza indebolire gate per ottenere il verde.
6. **Updater/installazione:** richiedono integrazione Qt dedicata; non riutilizzare il vecchio helper per un nuovo nome EXE senza test di versione, provenance, ACL, rollback, UAC e readiness.
7. **Non fare merge né pubblicazione** finché parità completa, smoke del binario, verifica visiva, QA Windows su ambiente usa-e-getta e test manuale non superano i gate.

## Comandi locali (Windows)

Dalla radice del repository:

\`\`\`powershell
python -m pip install -r requirements-dev.txt -r qt_lab/requirements.txt
python -m unittest discover -s qt_app/tests -p "test_*.py" -v
python qt_app/main.py
python qt_app/main.py --smoke-test --capture build/qt-app/source.png
\`\`\`

Il workflow \`Panacea Qt Migration QA\` produce un candidato portabile isolato e uno screenshot solo dopo test su Windows; il pacchetto si chiama \`PanaceaQtCandidate.exe\`, distinto dal prodotto stabile.

## Sequenza restante

1. Adattare schermate e letture in modalità live con UX e accessibilità confrontabili alla V2.
2. Abilitare progressivamente singole operazioni, sempre con guardrail e test fixture.
3. Riprodurre e verificare Quick Cleanup, Resurrection e Turbo con casi cancellazione, fallimento e completamento incerto.
4. Reintegrare aggiornamento/installer per il nuovo EXE con test di sicurezza Windows e rollback.
5. Misurare start-up, navigazione, RAM e dimensione del pacchetto finale a parità funzionale; solo allora valutare merge e release.

**Non confondere questo checkpoint con migrazione conclusa.**

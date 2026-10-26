# Panacea 2.0.2 — FASE 1: UX e revisione IT/EN

- **Pulizia rapida:** azione centrata senza etichetta o barra inattiva; avanzamento, errori, risultati e log visibili quando effettivi, conferme conservate. Nessuna modifica al motore.
- **Diagnostica:** pulsante “Crea punto di ripristino”; descrizione ottimizzazione unità comprensibile, senza introdurre termini TRIM/deframmentazione. Comandi SFC/DISM/rete invariati.
- **Manutenzione guidata:** disposizione 5+5 sopra 1180 unità logiche di viewport; griglie 3/2/1 per schermi più stretti; numerazione, stati, dieci informazioni espandibili e conferma di rischio conservate.
- **Audit bilingue:** etichette, stato aggiornamenti Windows, messaggi/diagnostica pulizia, output e motivi di esclusione, conferme operazioni, messaggi di annullamento, updater, dialoghi e stato della sequenza. Traduzione dei nomi operazione nei messaggi generati dinamicamente.
- **Verifica richiesta:** test regressione, Ruff, pytest, build, Windows GUI screenshot IT/EN 100/125/150% e integrazioni isolate. La simulazione widget scaling del runner non certifica il DPI fisico sul PC dell'utente.
- **Fuori fase:** tempi della prima apertura/navigazione. L'output arbitrario restituito da Windows/PowerShell resta integrale anziché tradotto in modo potenzialmente inesatto.
- **Release:** solo PR #5 draft; nessun merge, tag, release o test distruttivo sul PC personale.

# Panacea Qt Quick Lab — confronto isolato

Prototipo **read-only** costruito con PySide6 e Qt Quick. Non sostituisce, non installa, non aggiorna e non eleva Panacea. Usa la palette blu/oro del progetto e cinque destinazioni visivamente rappresentative, con costruzione lazy delle pagine e cache delle visite successive.

## Perimetro

- **Reale:** navigazione fra cinque sezioni, layout responsive, scrolling, monitoraggio CPU/RAM/disco (solo quando avviato normalmente), rendering Qt Quick.
- **Solo rappresentazione:** schede di pulizia, riparazione, Turbo e Resurrect. I nomi delle operazioni non sono pulsanti funzionanti. Non tocca servizi, registro, filesystem, aggiornamenti o rete.
- **Non verificato automaticamente:** vantaggio grafico percepito sul dispositivo, compatibilità Windows/DPI reale, comparabilità diretta delle latenze con Tk, memoria nel funzionamento quotidiano.

## Esecuzione da sorgenti (Windows, senza admin)

Dalla radice del repository:

    python -m pip install -r qt_lab/requirements.txt
    python qt_lab/main.py

Misura senza operazioni di manutenzione:

    python qt_lab/main.py --smoke-test --report build/qt-lab/source.json --capture build/qt-lab/dashboard.png

## Build QA

Il workflow indipendente **Panacea Qt Quick Lab** produce una cartella standalone PanaceaQtLab, uno ZIP, screenshot, smoke e dati di navigazione. Il pacchetto è **solo QA**, non firmato e non pubblicato come release. Non contiene il sistema di auto-update della versione stabile.

## Interpretazione dei numeri

Lo smoke misura import/creazione dell'engine Qt e cambio tab con drain degli eventi. **Non misura il primo pixel dipinto dal compositor**: non riportarlo come vera latenza visiva. Le prove Windows della versione Tk sono acquisite nello stesso runner con lo script esistente; il confronto rimane indicativo perché la quantità di widget, il percorso di navigazione e il rendering differiscono.

Decisione di adozione **solo dopo** feedback grafico/funzionale e misure attendibili sullo stesso PC: se Qt Quick non offre un beneficio netto rispetto a costi, dimensioni e manutenibilità, eliminare il branch senza toccare la versione principale. La migrazione di operazioni Windows, permessi, firma/installazione e updater richiederà uno scope successivo, mai implicito.

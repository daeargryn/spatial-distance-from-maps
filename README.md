# spatial-distance-from-maps

## Installazione dipendenze

```bash
pip install requests pandas ...

```

## synth_gen.py

Ecco lo script aggiornato e semplificato. Non richiede alcun file in input: accetta unicamente il nome della città (`--city`, default `"Roma"`), il numero di righe (`--rows`, default `1000`) e un raggio opzionale in chilometri (`--radius-km`, default `10.0`) attorno alle coordinate del centro urbano.

Interroga prima Nominatim per centrare la città, quindi estrae da OpenStreetMap (via Overpass API) solo **indirizzi reali esistenti** (strade e numeri civici mappati con le loro coordinate effettive) all'interno del raggio richiesto.

### Struttura delle colonne generate

Il file CSV prodotto contiene direttamente tutte le colonne necessarie per alimentare i precedenti script di calcolo distanza o geocodifica:

* `id`: Identificativo sintetico sequenziale (`LOC_000001`).
* `location`: Indirizzo esteso (`Via Garibaldi 12, Roma`).
* `street`: Solo via e numero civico (`Via Garibaldi 12`).
* `cap`: Codice postale (se presente su OSM).
* `city`: Nome del comune.
* `latitude`, `longitude`: Coordinate geografiche reali dell'immobile/civico.

### Esempi di esecuzione

* **Default (1000 righe su Roma entro 10 km):**
```bash
python synth_gen.py

```


* **Personalizzazione città, raggio e righe:**
```bash
python synth_gen.py --city "Bologna" --radius-km 7.5 --rows 500 -o bologna_dataset.csv

```

* **Default (1000 righe per Roma, salvato in `synthetic_addresses_roma.csv`):**
```bash
python synth_gen.py

```

* **Città personalizzata e 5000 righe:**
```bash
python synth_gen.py --city "Milano" --rows 5000 -o output/milano_test.csv
```

## cap_retrieval.py

Ecco uno script Python che estrae strade e indirizzi **reali** attorno alla città specificata interrogando l'API Overpass di OpenStreetMap (tramite `requests`), li campiona per generare le righe richieste e assegna numeri civici plausibili o reali.

Lo script include anche una fallback di caching per evitare chiamate ripetute a Overpass se lo lanci più volte per la stessa città.

### Esempi di esecuzione

* **Test con lo script precedente:**
Puoi passare direttamente l'output di questo generatore allo script che cerca i CAP:
```bash
python cap_retrieval.py synthetic_addresses_roma.csv --id-col id --loc-col location

```

### coords_retrieval.py

Ecco lo script Python completo che utilizza il geocoder **Photon** integrato con il wrapper `RateLimiter` di GeoPy (sostituendo il ciclo manuale di sleep con retry/delay automatici).

Lo script concatena le componenti dell'indirizzo (`street`, `cap`, `location`), applica gli opzionali `--pre` e `--suff`, ed estrae l'indirizzo formattato completo (`full`), la latitudine (`lat`) e la longitudine (`long`).

### Esempi di utilizzo da riga di comando

* **Esecuzione standard (output ridotto `<ID>,full,lat,long` in `./geocoded.csv`):**
```bash
python coords_retrieval.py dati.csv --id-col ID --street-col Via --cap-col CAP --loc-col Citta

```


* **Con file Excel, delay personalizzato, retry e output completo (`--full`):**
```bash
python coords_retrieval.py indirizzi.xlsx --excel \
  --id-col CodiceCliente \
  --street-col Indirizzo \
  --cap-col CodicePostale \
  --loc-col Comune \
  --suff ", Italia" \
  --delay 1.0 \
  --max-retries 4 \
  --full \
  -o output/clienti_geocoded.csv
```

## distance_computation.py

Ecco lo script completo. Genera tutte le coppie ordinate non identiche ($N \times (N - 1)$) usando `itertools.permutations`, gestisce la selezione del backend di routing (GraphHopper se `--api` è valorizzato, altrimenti OSRM con il parametro `--alt` o default `3`), ed esporta i risultati in CSV.

---

### Esempi di utilizzo

* **Default (OSRM con `alternatives=3`):**
```bash
python distance_computation.py coordinate.csv --id-col ID --lat-col lat --lon-col long
```


* **OSRM con 5 alternative e output personalizzato:**

```bash
python distance_computation.py coordinate.csv --id-col ID --lat-col lat --lon-col long --alt 5 -o matrici_distanze.csv

```


* **GraphHopper con API Key:**
```bash
python distance_computation.py coordinate.csv --id-col ID --lat-col lat --lon-col long --api "TUA_API_KEY"

```
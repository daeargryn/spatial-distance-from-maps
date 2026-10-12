# Geospatial Data Processing & Routing Pipeline

A toolkit of Python CLI scripts for synthetic spatial data generation, address normalization, geocoding, and pairwise driving distance computation using OpenStreetMap (OSM), Nominatim, Photon, and OSRM/GraphHopper.

---

## Installation & Dependencies

Install required Python libraries:

```bash
pip install pandas requests geopy osmnx

```

---

## Scripts

### synth_gen.py

Generates a synthetic CSV dataset containing real physical addresses, street numbers, postcodes, and GPS coordinates sampled from OpenStreetMap within a specified radius around a target city or municipality.

* **Engine:** Uses `osmnx` to query house-level geometries (`addr:housenumber`) and `Photon` (via `geopy`) to locate the center coordinates and extract default fallback postcodes.
* **Hierarchical Toponym Resolution:** Traverses administrative tags (`addr:village`, `addr:town`, `addr:municipality`, `addr:city`) to ensure minor municipalities and towns are preserved accurately rather than being overwritten by the provincial capital.
* **Output Columns:** `id`, `location` (formatted with optional prefix/suffix), `street`, `<cap-col>` (customizable name, with fallback to prevent null values), `city`, `latitude`, `longitude`.

#### Command-Line Arguments

* `[--city]`: Target city/municipality name (default: `"Roma"`).
* `[--rows]`: Total rows to generate via sampling (default: `1000`).
* `[--radius-km]`: Search radius in kilometers from the center (default: `5.0`).
* `[--cap-col]`: Output column name for the postcode (default: `"CAP"`).
* `[--pre]`: Optional prefix prepended to the `location` string.
* `[--suff]`: Optional suffix appended to the `location` string.
* `[-o, --output]`: Output CSV file path (default: `synthetic_addresses_<city>.csv`).

#### Examples

```bash
# Generate 500 records within 3.5 km of Florence with custom CAP column
python synth_gen.py --city "Firenze" --rows 500 --radius-km 3.5 --cap-col CodicePostale

# Sample addresses around Acquappesa with prefixes/suffixes
python synth_gen.py --city "Acquappesa" --rows 200 --radius-km 4.0 --suff ", Italia" -o output/acquappesa.csv

```

---

### cap_retrieval.py

Recovers postal codes (CAP) for addresses or locality strings using OpenStreetMap's Nominatim geocoder.

* **Throttling & Retries:** Employs GeoPy's `RateLimiter` wrapper to enforce OSM usage policies (1 request/sec delay, automatic exponential retry on timeouts and temporary service disconnections).
* **Format Flexibility:** Supports both CSV and Excel inputs (`--excel`), allowing optional prefixes/suffixes to improve geocoding match accuracy.
* **Output Formats:** Produces a minimal CSV (`<id-col>,CAP`) by default, or preserves all original input columns and appends `CAP` when `--full` is specified.

#### Command-Line Arguments

* `input_path`: Path to the input file (CSV by default).
* `[--excel]`: Flag indicating the input file is an Excel spreadsheet (`.xlsx`, `.xls`).
* `--id-col`: Column name of the unique record identifier (required).
* `--loc-col`: Column name of the address/locality to search (required).
* `[--pre]`: Optional string prepended to each location query.
* `[--suff]`: Optional string appended to each location query.
* `[--full]`: Appends `CAP` to all input columns instead of exporting only ID and CAP.
* `[-o, --output]`: Output CSV file path (default: `./cap.csv`).

#### Examples

```bash
# Minimal output (<ID>,CAP) from CSV
python cap_retrieval.py indirizzi.csv --id-col ID_CLIENTE --loc-col Indirizzo

# Full dataset export from Excel with query suffix
python cap_retrieval.py clienti.xlsx --excel --id-col Codice --loc-col Comune --suff ", Italia" --full -o output/clienti_cap.csv

```

---

### coords_retrieval.py

Geocodes structured address components (`street`, `cap`, `location`) using the `Photon` geocoding service to retrieve normalized address strings and geographic coordinates (`lat`, `long`).

* **Query Assembly:** Concatenates street, postcode, and municipality while stripping missing/NaN values and applying optional prefixes and suffixes.
* **Throttling:** Uses GeoPy's `RateLimiter` with configurable delays (`--delay`) and retry thresholds (`--max-retries`).
* **Output Formats:** Exports `<id-col>,full,lat,long` by default, or appends the 3 columns to the full input dataset if `--full` is passed.

#### Command-Line Arguments

* `input_path`: Path to input file (CSV by default).
* `[--excel]`: Flag indicating an Excel file input.
* `--id-col`: Column name of the record identifier (required).
* `--street-col`: Column name of the street address (required).
* `--cap-col`: Column name of the postal code (required).
* `--loc-col`: Column name of the city/locality (required).
* `[--pre]`: Optional string prepended to the combined query.
* `[--suff]`: Optional string appended to the combined query.
* `[--delay]`: Minimum seconds between consecutive requests (default: `1.5`).
* `[--max-retries]`: Maximum attempts for failed requests (default: `3`).
* `[--full]`: Retains all input columns and appends `full`, `lat`, `long`.
* `[-o, --output]`: Output CSV path (default: `./geocoded.csv`).

#### Examples

```bash
# Geocode CSV input into minimal columns
python coords_retrieval.py sedi.csv --id-col ID --street-col Via --cap-col CAP --loc-col Citta

# Geocode Excel with custom rate limits and full column export
python coords_retrieval.py sedi.xlsx --excel --id-col Codice --street-col Indirizzo --cap-col CAP --loc-col Comune --delay 1.0 --max-retries 4 --full -o geocoded_full.csv

```

---

### distance_computation.py

Computes directional pairwise driving distance (in kilometers) and estimated travel duration (in minutes) for all non-identical ordered pairs ($N \times (N - 1)$) in a dataset.

* **Directionality:** Computes ordered permutations where $A \rightarrow B$ and $B \rightarrow A$ are evaluated independently to account for one-way systems, turn restrictions, and grade differences.
* **Dual Routing Backends:**
* **OSRM (Default):** Evaluates alternative routes (`--alt <int>`, default `3`) against public/self-hosted OSRM endpoints and selects the minimum distance route.
* **GraphHopper:** Invoked by passing `--api <KEY>`. Sends requests via GraphHopper's standard routing endpoint.


* **Output Columns:** `from_id`, `to_id`, `distance_km`, `duration_min`.

#### Command-Line Arguments

* `input_path`: CSV file containing unique IDs and coordinates.
* `--id-col`: Name of the record ID column (required).
* `--lat-col`: Name of the latitude column (required).
* `--lon-col`: Name of the longitude column (required).
* `[--api]`: GraphHopper API Key. When provided, routes via GraphHopper instead of OSRM.
* `[--alt]`: Number of alternatives requested in OSRM to approximate the shortest path (default: `3`).
* `[--delay]`: Delay in seconds between requests to prevent rate-limiting (default: `0.2`).
* `[-o, --output]`: Output CSV path (default: `./pairwise_distances.csv`).

#### Examples

```bash
# Compute all pairs with OSRM (evaluating 3 alternatives per pair)
python distance_computation.py points.csv --id-col ID --lat-col lat --lon-col long

# OSRM with 5 alternative routes and rate-limiting delay
python distance_computation.py points.csv --id-col ID --lat-col lat --lon-col long --alt 5 --delay 0.5 -o matrici_distanze.csv

# Compute all pairs using GraphHopper Cloud API
python distance_computation.py points.csv --id-col ID --lat-col lat --lon-col long --api "YOUR_GRAPHHOPPER_KEY" -o distanze_gh.csv

```

```

#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
import pandas as pd
from geopy.geocoders import Nominatim, Photon
from geopy.extra.rate_limiter import RateLimiter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recupera il CAP per una lista di località tramite OpenStreetMap Nominatim."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Percorso del file di input (CSV o Excel)."
    )
    parser.add_argument(
        "--excel",
        action="store_true",
        help="Specifica se il file di input è in formato Excel anziché CSV."
    )
    parser.add_argument(
        "--id-col",
        required=True,
        help="Nome della colonna contenente l'identificativo univoco."
    )
    parser.add_argument(
        "--loc-col",
        required=True,
        help="Nome della colonna contenente il luogo/indirizzo da geocodificare."
    )
    parser.add_argument(
        "--pre",
        default="",
        help="Testo facoltativo da anteporre a ciascuna località (es. 'Via ')."
    )
    parser.add_argument(
        "--suff",
        default="",
        help="Testo facoltativo da posporre a ciascuna località (es. ', Italia')."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Se specificato, esporta tutte le colonne originali più la colonna 'CAP'."
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path.cwd() / "cap.csv",
        help="Percorso del file CSV di output (default: 'cap.csv' nella directory corrente)."
    )
    return parser.parse_args()


def extract_postcode(location) -> str | None:
    """Estrae il CAP dal campo raw di geopy se presente."""
    if not location or not getattr(location, "raw", None):
        return None
    address = location.raw.get("address", {})
    return address.get("postcode")
    # return location.raw.get("postcode")


def main() -> None:
    args = parse_args()

    if not args.input_path.is_file():
        print(f"Errore: il file di input '{args.input_path}' non esiste.", file=sys.stderr)
        sys.exit(1)

    # 1. Caricamento del dataset
    try:
        if args.excel:
            df = pd.read_excel(args.input_path)
        else:
            df = pd.read_csv(args.input_path)
    except Exception as e:
        print(f"Errore durante la lettura del file: {e}", file=sys.stderr)
        sys.exit(1)

    # Verifica colonne richieste
    for col in (args.id_col, args.loc_col):
        if col not in df.columns:
            print(f"Errore: la colonna '{col}' non è presente nel file di input.", file=sys.stderr)
            sys.exit(1)

    # 2. Configurazione Nominatim e RateLimiter
    geolocator = Photon(user_agent="fuzzy")
    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=1.0,
        max_retries=2,
        error_wait_seconds=1.0,
        return_value_on_exception=None,
    )

    # 3. Preparazione query e geocodifica
    pre = f"{args.pre.strip()} " if args.pre.strip() else ""
    suff = f" {args.suff.strip()}" if args.suff.strip() else ""

    queries = df[args.loc_col].fillna("").astype(str).apply(
        lambda loc: f"{pre}{loc}{suff}".strip() if loc.strip() else ""
    )

    print(f"Avvio geocodifica di {len(df)} record...")
    
    postcodes = []
    for idx, q in enumerate(queries, 1):
        if not q:
            postcodes.append(None)
            continue
        
        # addressdetails=True restituisce la suddivisione amministrativa comprensiva del postcode
        loc_res = geocode(q, timeout=10)
        # input(loc_res.raw.get("properties").get("postcode"))
        # cap = extract_postcode(loc_res)
        cap = loc_res.raw.get("properties").get("postcode")
        postcodes.append(cap)
        # print(f"[{idx}/{len(queries)}] '{q}' -> CAP: {cap if cap else 'Non trovato'}, ACT: {df["cap"][idx-1]}")
        if cap is None:
            print("Cap non trovato per", q)
        if int(cap) != int(df["cap"][idx-1]):
            print("CAP diversi", f"comp: {cap}, act:{df["cap"][idx-1]}")
            print(df["location"][idx-1])

    # 4. Formattazione e salvataggio output
    if args.full:
        df["CAP"] = postcodes
        out_df = df
    else:
        out_df = pd.DataFrame({
            args.id_col: df[args.id_col],
            "CAP": postcodes
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.output, index=False, encoding="utf-8")
    print(f"\nSalvataggio completato con successo in: {args.output.resolve()}")


if __name__ == "__main__":
    main()
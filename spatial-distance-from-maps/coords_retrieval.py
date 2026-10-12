#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
import pandas as pd
from geopy.geocoders import Photon
from geopy.extra.rate_limiter import RateLimiter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recupera indirizzo completo, latitudine e longitudine tramite geocoder Photon."
    )
    parser.add_argument(
        "input_path",
        type=Path,
        help="Percorso del file di input (CSV o Excel)."
    )
    parser.add_argument(
        "--excel",
        action="store_true",
        help="Specifica se il file di input è in formato Excel (default: CSV)."
    )
    parser.add_argument(
        "--id-col",
        required=True,
        help="Nome della colonna contenente l'ID univoco."
    )
    parser.add_argument(
        "--street-col",
        required=True,
        help="Nome della colonna contenente la via/indirizzo."
    )
    parser.add_argument(
        "--cap-col",
        required=True,
        help="Nome della colonna contenente il CAP."
    )
    parser.add_argument(
        "--loc-col",
        required=True,
        help="Nome della colonna contenente la località/città."
    )
    parser.add_argument(
        "--pre",
        default="",
        help="Testo facoltativo da anteporre alla query."
    )
    parser.add_argument(
        "--suff",
        default="",
        help="Testo facoltativo da posporre alla query."
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Numero massimo di tentativi in caso di errore (default: 3)."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Intervallo minimo in secondi tra richieste consecutive (default: 1.5)."
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Se impostato, mantiene tutte le colonne originali e appende 'full', 'lat', 'long'."
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path.cwd() / "geocoded.csv",
        help="Percorso del file CSV di output (default: 'geocoded.csv' nella directory corrente)."
    )
    return parser.parse_args()


def build_query(row: pd.Series, street_col: str, cap_col: str, loc_col: str, pre: str, suff: str) -> str:
    """Compone la query unendo via, CAP e località evitando spazi vuoti multipli."""
    parts = []
    
    for col in (street_col, cap_col, loc_col):
        val = str(row[col]).strip() if pd.notna(row[col]) else ""
        if val and val.lower() != "nan":
            parts.append(val)
            
    base_query = ", ".join(parts)
    if not base_query:
        return ""
        
    pre_str = f"{pre.strip()} " if pre.strip() else ""
    suff_str = f" {suff.strip()}" if suff.strip() else ""
    
    return f"{pre_str}{base_query}{suff_str}".strip()


def main() -> None:
    args = parse_args()

    if not args.input_path.is_file():
        print(f"Errore: il file '{args.input_path}' non esiste.", file=sys.stderr)
        sys.exit(1)

    # 1. Caricamento del dataset
    try:
        if args.excel:
            df = pd.read_excel(args.input_path)
        else:
            df = pd.read_csv(args.input_path)
    except Exception as e:
        print(f"Errore durante la lettura del dataset: {e}", file=sys.stderr)
        sys.exit(1)

    # Controllo presenza colonne
    required_cols = [args.id_col, args.street_col, args.cap_col, args.loc_col]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"Errore: colonne mancanti nel file: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # 2. Configurazione Photon e RateLimiter
    geolocator = Photon(timeout=10)
    geocode = RateLimiter(
        geolocator.geocode,
        min_delay_seconds=args.delay,
        max_retries=args.max_retries,
        error_wait_seconds=args.delay,
        return_value_on_exception=None,
    )

    # 3. Composizione ed esecuzione geocodifica
    print(f"Avvio elaborazione di {len(df)} record con Photon (delay: {args.delay}s, retries: {args.max_retries})...")
    
    full_addresses = []
    latitudes = []
    longitudes = []

    for idx, (_, row) in enumerate(df.iterrows(), 1):
        query = build_query(row, args.street_col, args.cap_col, args.loc_col, args.pre, args.suff)

        if not query:
            full_addresses.append(None)
            latitudes.append(None)
            longitudes.append(None)
            continue

        location = geocode(query)

        if location:
            full_addresses.append(location.address)
            latitudes.append(location.latitude)
            longitudes.append(location.longitude)
            status = f"Trovato: {location.latitude:.5f}, {location.longitude:.5f}"
        else:
            full_addresses.append(None)
            latitudes.append(None)
            longitudes.append(None)
            status = "Non trovato"

        print(f"[{idx}/{len(df)}] '{query}' -> {status}")

    # 4. Creazione e salvataggio dell'output
    if args.full:
        out_df = df.copy()
        out_df["full"] = full_addresses
        out_df["lat"] = latitudes
        out_df["long"] = longitudes
    else:
        out_df = pd.DataFrame({
            args.id_col: df[args.id_col],
            "full": full_addresses,
            "lat": latitudes,
            "long": longitudes,
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.output, index=False, encoding="utf-8")
    print(f"\nSalvataggio completato: {args.output.resolve()}")


if __name__ == "__main__":
    main()
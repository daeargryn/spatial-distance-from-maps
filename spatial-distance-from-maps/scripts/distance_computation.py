#!/usr/bin/env python3
import argparse
import itertools
import sys
import time
from pathlib import Path
import pandas as pd
import requests


def get_shortest_driving_distance_gh(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
    api_key: str,
) -> dict | None:
    url = "https://graphhopper.com/api/1/route"
    clean_key = api_key.strip()

    payload = {
        "profile": "car",
        "points": [
            [float(lon1), float(lat1)],
            [float(lon2), float(lat2)]
        ],
        "points_encoded": False,
        "instructions": False,
        "elevation": False
    }

    params = {"key": clean_key}

    try:
        res = requests.post(url, json=payload, params=params, timeout=10)
        if not res.ok:
            try:
                err_json = res.json()
                print(f"GraphHopper API Error Details: {err_json}", file=sys.stderr)
            except Exception:
                print(f"GraphHopper Raw Response: {res.text}", file=sys.stderr)
            return None

        data = res.json()
        paths = data.get("paths", [])
        if paths:
            route = paths[0]
            return {
                "distance_km": round(route["distance"] / 1000.0, 2),
                "duration_min": round(route["time"] / (1000.0 * 60.0), 1)
            }
    except requests.RequestException as e:
        print(f"Errore di rete GH: {e}", file=sys.stderr)
        return None

    return None


def get_shortest_driving_distance_osrm(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
    alternatives: int = 3
) -> dict | None:
    url = (
        f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        f"?overview=false&alternatives={alternatives}"
    )
    try:
        res = requests.get(url, timeout=10).json()
        if res.get("code") == "Ok" and res.get("routes"):
            shortest_route = min(res["routes"], key=lambda r: r["distance"])
            return {
                "distance_km": round(shortest_route["distance"] / 1000, 2),
                "duration_min": round(shortest_route["duration"] / 60, 1)
            }
    except requests.RequestException as e:
        print(f"Errore di rete OSRM: {e}", file=sys.stderr)
        return None

    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calcola le distanze di guida punto a punto per tutte le coppie ordinate di un dataset."
    )
    parser.add_argument("input_path", type=Path, help="Percorso del file CSV di input.")
    parser.add_argument("--id-col", required=True, help="Nome della colonna ID.")
    parser.add_argument("--lat-col", required=True, help="Nome della colonna latitudine.")
    parser.add_argument("--lon-col", required=True, help="Nome della colonna longitudine.")
    parser.add_argument(
        "--api",
        type=str,
        default=None,
        help="API Key di GraphHopper. Se specificata, usa GraphHopper invece di OSRM."
    )
    parser.add_argument(
        "--alt",
        type=int,
        default=None,
        help="Numero di rotte alternative per OSRM (usato solo se --api non è valorizzato; default: 3)."
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Ritardo in secondi tra le richieste per evitare rate-limiting (default: 0.2s)."
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path.cwd() / "pairwise_distances.csv",
        help="Percorso del CSV di output (default: pairwise_distances.csv nella CWD)."
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.input_path.is_file():
        print(f"Errore: il file '{args.input_path}' non esiste.", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(args.input_path)

    for col in (args.id_col, args.lat_col, args.lon_col):
        if col not in df.columns:
            print(f"Errore: la colonna '{col}' non è presente nel CSV.", file=sys.stderr)
            sys.exit(1)

    # Pulizia coordinate nulle o non convertibili
    df = df.dropna(subset=[args.id_col, args.lat_col, args.lon_col]).copy()
    df[args.lat_col] = pd.to_numeric(df[args.lat_col], errors="coerce")
    df[args.lon_col] = pd.to_numeric(df[args.lon_col], errors="coerce")
    df = df.dropna(subset=[args.lat_col, args.lon_col])

    # Determinazione backend di calcolo
    use_gh = args.api is not None and len(args.api.strip()) > 0
    osrm_alternatives = args.alt if args.alt is not None else 3

    backend_desc = "GraphHopper" if use_gh else f"OSRM (alternatives={osrm_alternatives})"
    print(f"Backend selezionato: {backend_desc}")

    # Estrazione record per permutazioni
    records = df[[args.id_col, args.lat_col, args.lon_col]].to_dict("records")
    pairs = list(itertools.permutations(records, 2))
    total_pairs = len(pairs)

    print(f"Località valide: {len(records)} -> Coppie totali da calcolare (N*(N-1)): {total_pairs}")

    results = []
    for idx, (origin, destination) in enumerate(pairs, 1):
        from_id = origin[args.id_col]
        to_id = destination[args.id_col]
        lat1, lon1 = origin[args.lat_col], origin[args.lon_col]
        lat2, lon2 = destination[args.lat_col], destination[args.lon_col]

        if use_gh:
            route = get_shortest_driving_distance_gh(lon1, lat1, lon2, lat2, args.api)
        else:
            route = get_shortest_driving_distance_osrm(lon1, lat1, lon2, lat2, osrm_alternatives)

        dist = route["distance_km"] if route else None
        duration = route["duration_min"] if route else None

        results.append({
            "from_id": from_id,
            "to_id": to_id,
            "distance_km": dist,
            "duration_min": duration,
        })

        status = f"{dist} km ({duration} min)" if route else "Failed"
        print(f"[{idx}/{total_pairs}] {from_id} -> {to_id}: {status}")

        if args.delay > 0:
            time.sleep(args.delay)

    out_df = pd.DataFrame(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.output, index=False, encoding="utf-8")
    print(f"\nSalvataggio completato: {args.output.resolve()}")


if __name__ == "__main__":
    main()
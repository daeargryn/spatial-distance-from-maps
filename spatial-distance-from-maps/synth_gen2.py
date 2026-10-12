#!/usr/bin/env python3
import argparse
import random
import sys
from pathlib import Path
import pandas as pd
import requests

try:
    import osmnx as ox
except ImportError:
    print("Errore: la libreria 'osmnx' non è installata. Esegui: pip install osmnx", file=sys.stderr)
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un CSV sintetico con indirizzi e coordinate reali tramite OSMnx."
    )
    parser.add_argument(
        "--city",
        type=str,
        default="Roma",
        help="Città di riferimento (default: 'Roma')."
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=1000,
        help="Numero di righe/indirizzi da generare (default: 1000)."
    )
    parser.add_argument(
        "--radius-km",
        type=float,
        default=5.0,
        help="Raggio di ricerca in km attorno al centroide della città (default: 5.0)."
    )
    parser.add_argument(
        "--cap-col",
        type=str,
        default="CAP",
        help="Nome della colonna di output per il CAP (default: 'CAP')."
    )
    parser.add_argument(
        "--pre",
        type=str,
        default="",
        help="Prefisso opzionale da anteporre alla stringa 'location'."
    )
    parser.add_argument(
        "--suff",
        type=str,
        default="",
        help="Suffisso opzionale da posporre alla stringa 'location'."
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Percorso del file CSV di output (default: 'synthetic_addresses_<citta>.csv')."
    )
    return parser.parse_args()


# def get_city_coords_and_postcode(city: str) -> tuple[float, float, str]:
#     """Recupera le coordinate centrali e il CAP predefinito della città."""
#     url = "https://nominatim.openstreetmap.org/search"
#     params = {"q": city, "format": "json", "addressdetails": 1, "limit": 1}
#     headers = {"User-Agent": "osmnx_address_generator/1.0"}

#     try:
#         res = requests.get(url, params=params, headers=headers, timeout=10)
#         res.raise_for_status()
#         data = res.json()
#         if not data:
#             print(f"Errore: città '{city}' non trovata su Nominatim.", file=sys.stderr)
#             sys.exit(1)

#         lat = float(data[0]["lat"])
#         lon = float(data[0]["lon"])
#         fallback_cap = data[0].get("address", {}).get("postcode", "")
#         return lat, lon, fallback_cap
#     except Exception as e:
#         print(f"Errore durante il recupero dei dati città: {e}", file=sys.stderr)
#         sys.exit(1)

import sys
from geopy.geocoders import Photon
from geopy.exc import GeocoderServiceError


def get_city_coords_and_postcode(city: str) -> tuple[float, float, str]:
    """Recupera le coordinate centrali e il CAP di default della città usando Photon via GeoPy."""
    geolocator = Photon(timeout=10)

    try:
        location = geolocator.geocode(city)
        if not location:
            print(f"Errore: città '{city}' non trovata su Photon.", file=sys.stderr)
            sys.exit(1)

        lat = float(location.latitude)
        lon = float(location.longitude)

        # Photon inserisce i dettagli territoriali in location.raw["properties"]
        properties = location.raw.get("properties", {}) if location.raw else {}
        fallback_cap = str(properties.get("postcode", "") or "").strip()

        return lat, lon, fallback_cap

    except GeocoderServiceError as e:
        print(f"Errore durante l'interrogazione Photon: {e}", file=sys.stderr)
        sys.exit(1)


def fetch_osm_geometries(lat: float, lon: float, radius_meters: int):
    """Interroga OSMnx gestendo la compatibilità tra le versioni 1.x e 2.x."""
    tags = {"addr:housenumber": True}
    
    # Nelle versioni moderne di osmnx si usa features_from_point, nelle precedenti geometries_from_point
    if hasattr(ox, "features_from_point"):
        return ox.features_from_point((lat, lon), tags=tags, dist=radius_meters)
    elif hasattr(ox, "geometries_from_point"):
        return ox.geometries_from_point((lat, lon), tags=tags, dist=radius_meters)
    else:
        raise AttributeError("Impossibile trovare 'features_from_point' o 'geometries_from_point' in osmnx.")


def main() -> None:
    args = parse_args()
    clean_city_name = args.city.lower().replace(" ", "_")
    output_path = args.output or Path.cwd() / f"synthetic_addresses_{clean_city_name}.csv"
    radius_meters = int(args.radius_km * 1000)

    # 1. Recupero centroide e CAP base della città
    lat, lon, fallback_cap = get_city_coords_and_postcode(args.city)
    print(f"Centro di '{args.city}' individuato: ({lat:.5f}, {lon:.5f}) - CAP fallback: '{fallback_cap}'")

    # 2. Download geometrie con OSMnx
    print(f"Estrazione indirizzi e numeri civici entro {args.radius_km} km con OSMnx...")
    try:
        gdf = fetch_osm_geometries(lat, lon, radius_meters)
    except Exception as e:
        print(f"Errore durante l'interrogazione con OSMnx: {e}", file=sys.stderr)
        sys.exit(1)

    if gdf.empty:
        print("Nessun civico trovato nel raggio selezionato. Prova ad aumentare --radius-km.", file=sys.stderr)
        sys.exit(1)

    # 3. Filtraggio e normalizzazione degli indirizzi
    # Calcolo coordinate dei centroidi (gestisce sia Point che Poligoni/edifici)
    centroids = gdf.geometry.centroid
    gdf["latitude"] = centroids.y
    gdf["longitude"] = centroids.x

    # Verifica colonne richieste
    if "addr:street" not in gdf.columns or "addr:housenumber" not in gdf.columns:
        print("Il dataset estratto non contiene informazioni sufficienti su vie e numeri civici.", file=sys.stderr)
        sys.exit(1)

    # Mantieni solo i record con via e civico validi
    valid = gdf.dropna(subset=["addr:street", "addr:housenumber"]).copy()
    if valid.empty:
        print("Nessun record valido con via e numero civico trovato.", file=sys.stderr)
        sys.exit(1)

    # Gestione colonne opzionali se presenti nel grafo OSM
    postcode_series = valid["addr:postcode"] if "addr:postcode" in valid.columns else pd.Series(index=valid.index, dtype=str)
    city_series = valid["addr:city"] if "addr:city" in valid.columns else pd.Series(index=valid.index, dtype=str)

    pool = []
    for idx, row in valid.iterrows():
        street = str(row["addr:street"]).strip()
        house_num = str(row["addr:housenumber"]).strip()
        cap_val = postcode_series.get(idx)
        city_val = city_series.get(idx)

        cap_final = str(cap_val).strip() if pd.notna(cap_val) and str(cap_val).strip() else fallback_cap
        city_final = str(city_val).strip() if pd.notna(city_val) and str(city_val).strip() else args.city

        pool.append({
            "street": f"{street} {house_num}",
            "cap": cap_final,
            "city": city_final,
            "latitude": row["latitude"],
            "longitude": row["longitude"]
        })

    print(f"Pool di indirizzi reali estratti: {len(pool)}")

    # 4. Campionamento e composizione righe
    selected = random.choices(pool, k=args.rows)
    pre_str = f"{args.pre.strip()} " if args.pre.strip() else ""
    suff_str = f" {args.suff.strip()}" if args.suff.strip() else ""

    records = []
    for i, item in enumerate(selected, 1):
        # Composizione stringa location con eventuale prefisso e suffisso
        raw_location = f"{item['street']}, {item['city']}"
        location = f"{pre_str}{raw_location}{suff_str}".strip()

        records.append({
            "id": f"LOC_{i:06d}",
            "location": location,
            "street": item["street"],
            args.cap_col: item["cap"],
            "city": item["city"],
            "latitude": item["latitude"],
            "longitude": item["longitude"]
        })

    # 5. Esportazione CSV
    out_df = pd.DataFrame(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"\nSalvataggio completato: {output_path.resolve()} ({len(out_df)} righe)")


if __name__ == "__main__":
    main()
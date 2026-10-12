#!/usr/bin/env python3
import argparse
import random
import sys
from pathlib import Path
import pandas as pd
from geopy.exc import GeocoderServiceError
from geopy.geocoders import Photon

try:
    import osmnx as ox
except ImportError:
    print(
        "Errore: la libreria 'osmnx' non è installata. Esegui: pip install osmnx",
        file=sys.stderr,
    )
    sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un CSV sintetico con indirizzi e coordinate reali tramite OSMnx con gerarchia toponimi corretta."
    )
    parser.add_argument(
        "--city",
        type=str,
        default="Roma",
        help="Città o comune di riferimento (default: 'Roma').",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=1000,
        help="Numero di righe/indirizzi da generare (default: 1000).",
    )
    parser.add_argument(
        "--radius-km",
        type=float,
        default=5.0,
        help="Raggio di ricerca in km attorno al centroide (default: 5.0).",
    )
    parser.add_argument(
        "--cap-col",
        type=str,
        default="cap",
        help="Nome della colonna di output per il CAP (default: 'CAP').",
    )
    parser.add_argument(
        "--pre",
        type=str,
        default="",
        help="Prefisso opzionale da anteporre alla stringa 'location'.",
    )
    parser.add_argument(
        "--suff",
        type=str,
        default="",
        help="Suffisso opzionale da posporre alla stringa 'location'.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Percorso del file CSV di output (default: 'synthetic_addresses_<citta>.csv').",
    )
    return parser.parse_args()


def extract_hierarchical_city_photon(properties: dict, fallback_name: str) -> str:
    """Risolve il toponimo a cascata da Photon privilegiando il livello più locale."""
    candidates = [
        properties.get("village"),
        properties.get("town"),
        properties.get("municipality"),
        properties.get("city"),
        properties.get("name"),
    ]
    for val in candidates:
        if val and str(val).strip():
            return str(val).strip()
    return fallback_name


def get_city_coords_and_postcode(city: str) -> tuple[float, float, str, str]:
    """Recupera coordinate, CAP di default e nome normalizzato tramite Photon."""
    geolocator = Photon(timeout=10)

    try:
        location = geolocator.geocode(city)
        if not location:
            print(f"Errore: comune '{city}' non trovato su Photon.", file=sys.stderr)
            sys.exit(1)

        lat = float(location.latitude)
        lon = float(location.longitude)

        properties = location.raw.get("properties", {}) if location.raw else {}
        fallback_cap = str(properties.get("postcode", "") or "").strip()
        resolved_city_name = extract_hierarchical_city_photon(properties, city)

        return lat, lon, fallback_cap, resolved_city_name

    except GeocoderServiceError as e:
        print(f"Errore durante l'interrogazione Photon: {e}", file=sys.stderr)
        sys.exit(1)


def fetch_osm_geometries(lat: float, lon: float, radius_meters: int):
    """Interroga OSMnx gestendo la compatibilità tra versioni 1.x e 2.x."""
    tags = {"addr:housenumber": True}
    if hasattr(ox, "features_from_point"):
        return ox.features_from_point((lat, lon), tags=tags, dist=radius_meters)
    elif hasattr(ox, "geometries_from_point"):
        return ox.geometries_from_point((lat, lon), tags=tags, dist=radius_meters)
    else:
        raise AttributeError(
            "Impossibile trovare 'features_from_point' o 'geometries_from_point' in osmnx."
        )


def extract_hierarchical_city_osm(row: pd.Series, default_name: str) -> str:
    """Isola il comune reale dal record OSM controllando i diversi tag di livello locale."""
    priority_tags = [
        "addr:village",
        "addr:town",
        "addr:municipality",
        "addr:city",
        "addr:subdistrict",
    ]
    for tag in priority_tags:
        if tag in row and pd.notna(row[tag]) and str(row[tag]).strip():
            return str(row[tag]).strip()
    return default_name


def main() -> None:
    args = parse_args()
    clean_city_name = args.city.lower().replace(" ", "_")
    output_path = (
        args.output or Path.cwd() / f"synthetic_addresses_{clean_city_name}.csv"
    )
    radius_meters = int(args.radius_km * 1000)

    # 1. Recupero centroide, CAP e toponimo corretto tramite Photon
    lat, lon, fallback_cap, photon_city = get_city_coords_and_postcode(args.city)
    print(
        f"Punto di riferimento '{args.city}' risolto come: '{photon_city}' ({lat:.5f}, {lon:.5f}) - cap fallback: '{fallback_cap}'"
    )

    # 2. Download elementi da OSMnx
    print(f"Download geometrie nel raggio di {args.radius_km} km...")
    try:
        gdf = fetch_osm_geometries(lat, lon, radius_meters)
    except Exception as e:
        print(f"Errore durante l'interrogazione con OSMnx: {e}", file=sys.stderr)
        sys.exit(1)

    if gdf.empty:
        print(
            "Nessun civico trovato nel raggio specificato. Prova ad aumentare --radius-km.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Calcolo coordinate dei baricentri
    centroids = gdf.geometry.centroid
    gdf["latitude"] = centroids.y
    gdf["longitude"] = centroids.x

    # Controllo tag minimi
    if "addr:street" not in gdf.columns or "addr:housenumber" not in gdf.columns:
        print(
            "I dati scaricati non contengono colonne relative a vie e civici.",
            file=sys.stderr,
        )
        sys.exit(1)

    valid = gdf.dropna(subset=["addr:street", "addr:housenumber"]).copy()
    if valid.empty:
        print("Nessun record valido con via e civico presente.", file=sys.stderr)
        sys.exit(1)

    has_postcode = "addr:postcode" in valid.columns

    # 3. Costruzione pool normalizzato
    pool = []
    for _, row in valid.iterrows():
        street = str(row["addr:street"]).strip()
        house_num = str(row["addr:housenumber"]).strip()

        # Risoluzione CAP
        raw_cap = (
            str(row["addr:postcode"]).strip()
            if has_postcode and pd.notna(row["addr:postcode"])
            else ""
        )
        final_cap = raw_cap if raw_cap else fallback_cap

        # Risoluzione gerarchica del comune
        final_city = extract_hierarchical_city_osm(row, photon_city)

        pool.append(
            {
                "street": f"{street} {house_num}",
                "cap": final_cap,
                "city": final_city,
                "latitude": row["latitude"],
                "longitude": row["longitude"],
            }
        )

    print(f"Pool indirizzi reali estratti: {len(pool)}")

    # 4. Campionamento e generazione CSV
    selected = random.choices(pool, k=args.rows)
    pre_str = f"{args.pre.strip()} " if args.pre.strip() else ""
    suff_str = f" {args.suff.strip()}" if args.suff.strip() else ""

    records = []
    for i, item in enumerate(selected, 1):
        raw_location = f"{item['street']}, {item['city']}"
        location_val = f"{pre_str}{raw_location}{suff_str}".strip()

        records.append(
            {
                "id": f"LOC_{i:06d}",
                "location": location_val,
                "street": item["street"],
                args.cap_col: item["cap"],
                "city": item["city"],
                "latitude": item["latitude"],
                "longitude": item["longitude"],
            }
        )

    out_df = pd.DataFrame(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"File salvato con successo in: {output_path.resolve()}")


if __name__ == "__main__":
    main()
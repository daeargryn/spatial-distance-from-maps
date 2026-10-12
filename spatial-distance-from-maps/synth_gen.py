#!/usr/bin/env python3
import argparse
import random
import sys
from pathlib import Path
import pandas as pd
import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Genera un CSV sintetico con indirizzi e coordinate reali entro un raggio da una città."
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
        help="Numero di righe/indirizzi sintetici da generare (default: 1000)."
    )
    parser.add_argument(
        "--radius-km",
        type=float,
        default=10.0,
        help="Raggio di ricerca in km attorno al centro della città (default: 10.0)."
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Percorso file CSV di output (default: 'synthetic_addresses_<citta>.csv')."
    )
    return parser.parse_args()


# def get_city_center(city: str) -> tuple[float, float]:
#     """Recupera le coordinate del centro città tramite Nominatim."""
#     url = "https://nominatim.openstreetmap.org/search"
#     params = {"q": city, "format": "json", "limit": 1}
#     headers = {"User-Agent": "synthetic_generator/2.0"}

#     try:
#         res = requests.get(url, params=params, headers=headers, timeout=10)
#         res.raise_for_status()
#         data = res.json()
#         if not data:
#             print(f"Errore: coordinate non trovate per la città '{city}'.", file=sys.stderr)
#             sys.exit(1)
#         return float(data[0]["lat"]), float(data[0]["lon"])
#     except Exception as e:
#         print(f"Errore nel geocoding della città: {e}", file=sys.stderr)
#         sys.exit(1)

def get_city_center_and_cap(city: str) -> tuple[float, float, str]:
    """Recupera coordinate e CAP predefinito della città tramite Nominatim."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": city, "format": "json", "addressdetails": 1, "limit": 1}
    headers = {"User-Agent": "synthetic_generator/2.1"}

    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json()
        if not data:
            print(f"Errore: città '{city}' non trovata.", file=sys.stderr)
            sys.exit(1)
            
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        fallback_cap = data[0].get("address", {}).get("postcode", "")
        return lat, lon, fallback_cap
    except Exception as e:
        print(f"Errore nel geocoding della città: {e}", file=sys.stderr)
        sys.exit(1)


# def fetch_real_addresses(lat: float, lon: float, radius_km: float) -> list[dict]:
#     """Estrae indirizzi completi reali (via, civico, coordinate) con Overpass API."""
#     radius_meters = int(radius_km * 1000)
#     overpass_url = "https://overpass-api.de/api/interpreter"

#     # Cerca elementi dotati sia di strada che di numero civico
#     query = f"""
#     [out:json][timeout:60];
#     (
#       node["addr:street"]["addr:housenumber"](around:{radius_meters},{lat},{lon});
#       way["addr:street"]["addr:housenumber"](around:{radius_meters},{lat},{lon});
#     );
#     out center 3000;
#     """

#     headers = {"User-Agent": "synthetic_generator/2.0"}
#     print(f"Interrogazione OSM Overpass nel raggio di {radius_km} km...")

#     try:
#         res = requests.post(overpass_url, data={"data": query}, headers=headers, timeout=65)
#         res.raise_for_status()
#         elements = res.json().get("elements", [])
#     except Exception as e:
#         print(f"Errore durante l'interrogazione Overpass: {e}", file=sys.stderr)
#         sys.exit(1)

#     addresses = []
#     for el in elements:
#         tags = el.get("tags", {})
#         street = tags.get("addr:street")
#         housenumber = tags.get("addr:housenumber")
#         postcode = tags.get("addr:postcode", "")
#         city_name = tags.get("addr:city", "")

#         # Coordinate: 'center' per i way, 'lat'/'lon' per i node
#         c_lat = el.get("lat") or el.get("center", {}).get("lat")
#         c_lon = el.get("lon") or el.get("center", {}).get("lon")

#         if street and housenumber and c_lat and c_lon:
#             addresses.append({
#                 "street": f"{street} {housenumber}",
#                 "postcode": postcode,
#                 "city": city_name,
#                 "latitude": c_lat,
#                 "longitude": c_lon
#             })

#     return addresses

OVERPASS_ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]


def fetch_real_addresses(lat: float, lon: float, radius_km: float, out=2000) -> list[dict]:
    """Estrae indirizzi civici reali ottimizzando la query e gestendo mirror di fallback."""
    radius_meters = int(radius_km * 1000)

    # Query ottimizzata: cerca solo elementi che hanno esplicitamente sia via che civico,
    # impostando un limite di estrazione (es. 2500) per evitare scansioni esaustive pesanti.
    query = f"""
    [out:json][timeout:120];
    (
      node["addr:street"]["addr:housenumber"](around:{radius_meters},{lat},{lon});
    );
    out {out};
    """

    headers = {"User-Agent": "synthetic_generator_fast/3.0"}

    for endpoint in OVERPASS_ENDPOINTS:
        print(f"Tentativo interrogazione Overpass su {endpoint}...")
        try:
            res = requests.post(
                endpoint,
                data={"data": query},
                headers=headers,
                timeout=60
            )
            res.raise_for_status()
            elements = res.json().get("elements", [])

            addresses = []
            for el in elements:
                tags = el.get("tags", {})
                street = tags.get("addr:street")
                housenumber = tags.get("addr:housenumber")
                c_lat = el.get("lat")
                c_lon = el.get("lon")

                if street and housenumber and c_lat and c_lon:
                    addresses.append({
                        "street": f"{street} {housenumber}",
                        "postcode": tags.get("addr:postcode", None),
                        "city": tags.get("addr:city", ""),
                        "latitude": c_lat,
                        "longitude": c_lon,
                    })

            if addresses:
                return addresses

        except requests.RequestException as e:
            print(f"Server {endpoint} non disponibile o in timeout ({e}). Provo il successivo...")

    print("Errore: tutti i server Overpass hanno risposto con timeout o errore.", file=sys.stderr)
    sys.exit(1)

def main() -> None:
    args = parse_args()
    clean_city_name = args.city.lower().replace(" ", "_")
    output_path = args.output or Path.cwd() / f"synthetic_addresses_{clean_city_name}.csv"

    # 1. Recupero centroide
    lat, lon, fallback_cap = get_city_center_and_cap(args.city)
    print(f"Centro città '{args.city}' individuato: {lat:.5f}, {lon:.5f}")

    # 2. Download indirizzi reali nel raggio
    pool = fetch_real_addresses(lat, lon, args.radius_km, int(args.rows * 10))
    if not pool:
        print(f"Nessun indirizzo completo trovato entro {args.radius_km} km. Prova ad aumentare il raggio.", file=sys.stderr)
        sys.exit(1)

    print(f"Trovati {len(pool)} indirizzi reali univoci nel raggio.")

    # 3. Campionamento con rimpiazzo per raggiungere il totale righe
    print(f"Generazione di {args.rows} record...")
    for item in pool:
        if item["city"] and item["postcode"] is None:
            pool.remove(item)
    selected_samples = random.choices(pool, k=args.rows)

    records = []
    for i, item in enumerate(selected_samples, 1):
        if not item["city"]:
            city_label = item["city"] if item["city"] else args.city
        # Durante la generazione dei record:
            cap_effettivo = item["postcode"] if item["postcode"] else fallback_cap
        records.append({
            "id": f"LOC_{i:06d}",
            # "location": f"{item['street']}, {city_label}",
            "location": f"{city_label}",
            "street": item["street"],
            "cap": cap_effettivo,  # Non sarà più NaN
            "city": city_label,
            "latitude": item["latitude"],
            "longitude": item["longitude"]
        })
        # records.append({
        #     "id": f"LOC_{i:06d}",
        #     # "location": f"{item['street']}, {city_label}",
        #     "location": f"{city_label}",
        #     "street": item["street"],
        #     "cap": item["postcode"],
        #     "city": city_label,
        #     "latitude": item["latitude"],
        #     "longitude": item["longitude"]
        # })

    # 4. Esportazione CSV
    df = pd.DataFrame(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"File generato con successo: {output_path.resolve()}")


if __name__ == "__main__":
    main()
import requests

# def get_driving_distance_osrm(lon1, lat1, lon2, lat2):
#     url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
#     res = requests.get(url).json()
    
#     if res.get("code") == "Ok":
#         meters = res["routes"][0]["distance"]
#         seconds = res["routes"][0]["duration"]
#         return {
#             "distance_km": round(meters / 1000, 2),
#             "duration_min": round(seconds / 60, 1)
#         }
#     return None


def get_shortest_driving_distance_osrm(lon1, lat1, lon2, lat2, alternatives=3):
    # Request up to 3 alternative routes
    url = (
        f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        f"?overview=false&alternatives={alternatives}"
    )
    res = requests.get(url).json()
    
    if res.get("code") == "Ok" and res.get("routes"):
        # Find the route with the minimum distance
        shortest_route = min(res["routes"], key=lambda r: r["distance"])
        
        return {
            "distance_km": round(shortest_route["distance"] / 1000, 2),
            "duration_min": round(shortest_route["duration"] / 60, 1)
        }
    return None

# Example: Lower Manhattan to Central Park South
# result = get_driving_distance_osrm(-74.0060, 40.7128, -73.9772, 40.7661)
# print(result)
# Output: {'distance_km': 7.82, 'duration_min': 18.4}


from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time

# Nominatim requires a custom user_agent name
# geolocator = Nominatim(user_agent="cosenza_routing_app")

from geopy.geocoders import Photon

# Drop-in replacement for Nominatim
# geolocator = Photon(user_agent="fuzzy_matcher")

addresses = [
#     # "Piazza dei Bruzi 1, Cosenza, Italy",
#     # "Corso Mazzini, Cosenza, Italy",
    "Via Guglielmo Marconi, Rende, Italy",
    "Via Don Carlo De Cardona 5, Mirto Crosia, Calabria, Italy"
]


import time
from geopy.geocoders import ArcGIS, Photon, Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# geolocator = Photon(user_agent="my_distance_app", timeout=10)
# geolocator = Photon(user_agent="fuzzy_matcher", timeout=10)
geolocator = Photon(timeout=10)

def safe_geocode(query, max_retries=3, delay=1.5):
    for attempt in range(1, max_retries + 1):
        try:
            return geolocator.geocode(query)
        except (GeocoderTimedOut, GeocoderUnavailable) as err:
            if attempt == max_retries:
                print(f"Failed after {max_retries} attempts: {err}")
                return None
            time.sleep(delay)




def get_cap(query: str, user_agent: str = "cap_finder_app") -> str | None:
    """
    Recupera il CAP per un indirizzo o una località usando Nominatim.
    
    :param query: Indirizzo o località (es. 'Piazza Maggiore, Bologna' o 'Roma, Italia')
    :param user_agent: Identificativo univoco richiesto dalla policy di OpenStreetMap
    :return: Stringa con il CAP se trovato, altrimenti None
    """
    geolocator = Nominatim(user_agent=user_agent)
    
    # Riprova fino a 2 volte in caso di timeout o micro-disconnessioni
    for attempt in range(2):
        try:
            # addressdetails=True forza la restituzione dell'albero dei dettagli amministrativi
            location = geolocator.geocode(query, addressdetails=True, timeout=10)
            
            if not location or not location.raw:
                return None
            
            address = location.raw.get("address", {})
            return address.get("postcode")
            
        except (GeocoderTimedOut, GeocoderUnavailable):
            if attempt < 1:
                time.sleep(1.0)
                continue
            return None
            
    return None

query = " S. Demetrio Co., Cosenza CS "
cap = get_cap(query=query)
print(f"The CAP for query <{query}> is {cap}.")
input()

# addresses = [
#       {
#           "street":"*Cardona*",
#           "country":"Italy"

#       }  
# ]

import os
import requests

with open("gh_api.txt") as f:
    api_key = f.readline()

def get_shortest_driving_distance_gh(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float,
    api_key: str,
) -> dict | None:
    url = "https://graphhopper.com/api/1/route"
    
    # Clean the key to avoid trailing spaces / newline issues
    clean_key = api_key.strip()

    # Minimal payload using the standard profile
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

    res = requests.post(url, json=payload, params=params, timeout=10)

    # If it fails, print GraphHopper's explicit diagnostic payload
    if not res.ok:
        try:
            err_json = res.json()
            print("GraphHopper API Error Details:", err_json)
        except Exception:
            print("GraphHopper Raw Response:", res.text)
        return None

    data = res.json()
    paths = data.get("paths", [])
    if paths:
        route = paths[0]
        return {
            "distance_km": round(route["distance"] / 1000.0, 2),
            "duration_min": round(route["time"] / (1000.0 * 60.0), 1)
        }

    return None

coordinates = []

for address in addresses:
    try:
        # Fetch the location
        location = geolocator.geocode(address, exactly_one=True)
        print(*[f"{x}\n" for x in location])
        input()
        
        if location:
            coordinates.append((location.latitude, location.longitude))
            print(f"Found: {address} -> {location.latitude}, {location.longitude}")
        else:
            print(f"Not found: {address}")
            coordinates.append(None)
            
    except GeocoderTimedOut:
        print(f"Timeout error for: {address}")
        coordinates.append(None)
        
    # CRITICAL: Nominatim strictly limits requests to 1 per second.
    # You MUST sleep between requests or you will get temporarily banned.
    time.sleep(1.1)

distances = []
for i, (lat1, long1) in enumerate(coordinates):
    for j, (lat2, long2) in enumerate(coordinates):
        if i == j:
            continue
        dist = "NOPE"
        dist = get_shortest_driving_distance_osrm(lon1=long1, lat1=lat1, lon2=long2, lat2=lat2)
        dist2 = get_shortest_driving_distance_gh(lon1=long1, lat1=lat1, lon2=long2, lat2=lat2, api_key=api_key)
        print(addresses[i], "--->", addresses[j])
        print("km:", dist["distance_km"], dist2)
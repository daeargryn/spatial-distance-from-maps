import requests

def get_driving_distance_osrm(lon1, lat1, lon2, lat2):
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
    res = requests.get(url).json()
    
    if res.get("code") == "Ok":
        meters = res["routes"][0]["distance"]
        seconds = res["routes"][0]["duration"]
        return {
            "distance_km": round(meters / 1000, 2),
            "duration_min": round(seconds / 60, 1)
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
geolocator = Photon(user_agent="fuzzy_matcher")

addresses = [
#     # "Piazza dei Bruzi 1, Cosenza, Italy",
#     # "Corso Mazzini, Cosenza, Italy",
    "Via Guglielmo Marconi, Rende, Italy",
    "Via Don Carlo De Cardona 5, Mirto Crosia, Calabria, Italy"
]


import time
from geopy.geocoders import Photon
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

geolocator = Photon(user_agent="my_distance_app", timeout=10)

def safe_geocode(query, max_retries=3, delay=1.5):
    for attempt in range(1, max_retries + 1):
        try:
            return geolocator.geocode(query)
        except (GeocoderTimedOut, GeocoderUnavailable) as err:
            if attempt == max_retries:
                print(f"Failed after {max_retries} attempts: {err}")
                return None
            time.sleep(delay)

# loc = safe_geocode("Via Don Carlo De Cardona 5, Mirto Crosia, Calabria, Italy")
loc = safe_geocode("Piretto, Lattarico, Calabria, Italy", 100, 0.1)
if loc:
    print(loc)
    print(loc.latitude, loc.longitude)
else:
    print("Not available")


input()

# addresses = [
#       {
#           "street":"*Cardona*",
#           "country":"Italy"

#       }  
# ]

coordinates = []

for address in addresses:
    try:
        # Fetch the location
        location = geolocator.geocode(address, exactly_one=False)
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
        dist = get_driving_distance_osrm(lon1=long1, lat1=lat1, lon2=long2, lat2=lat2)
        print(addresses[i], "--->", addresses[j], "km:", dist["distance_km"])
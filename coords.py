from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time

# Nominatim requires a custom user_agent name
geolocator = Nominatim(user_agent="cosenza_routing_app")

addresses = [
    "Piazza dei Bruzi 1, Cosenza, Italy",
    "Via Guglielmo Marconi, Rende, Italy",
    "Corso Mazzini, Cosenza, Italy"
]

coordinates = []

for address in addresses:
    try:
        # Fetch the location
        location = geolocator.geocode(address)
        
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
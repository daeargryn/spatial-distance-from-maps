import osmnx as ox
import networkx as nx

# 1. Define the target area
place = "Cosenza, Calabria, Italy"

# 2. Download the graph
# network_type='drive' fetches all drivable public streets.
# We add a custom_filter to strictly request roads tagged with surface=asphalt.
# WARNING: See the "Data Caveat" below regarding the custom filter.
custom_asphalt_filter = '["highway"]["surface"~"asphalt"]'

print("Downloading graph (this may take a few minutes)...")
# For all drivable roads: ox.graph_from_place(place, network_type='drive')
# G = ox.graph_from_place(
#     place, 
#     custom_filter=custom_asphalt_filter, 
#     simplify=True
# )
G = ox.graph_from_place(place, network_type='drive', simplify=True)
# ox.graph_from_bbox([x+0.02 for x in (39.3000, 16.2500,39.3300, 16.2500+0.01)], network_type='drive')

# 3. OSMnx automatically adds a 'length' attribute (in meters) to every edge.
# Let's print some basic stats about the graph
print(f"Number of nodes: {len(G.nodes)}")
print(f"Number of edges: {len(G.edges)}")

# 4. Compute Distance Between Two Points (Lat, Lon)
# Example coordinates in Cosenza province (e.g., Cosenza city to Rende)
point_a = (39.3000, 16.2500) # Latitude, Longitude
point_b = (39.3300, 16.2500) 

# Find the nearest graph nodes to these coordinates (requires X, Y -> Lon, Lat)
orig_node = ox.distance.nearest_nodes(G, point_a[1], point_a[0])
dest_node = ox.distance.nearest_nodes(G, point_b[1], point_b[0])

# Calculate the shortest path using Dijkstra's algorithm, weighted by 'length'
shortest_path = nx.shortest_path(G, orig_node, dest_node, weight='length')
distance_meters = nx.shortest_path_length(G, orig_node, dest_node, weight='length')

print(f"Distance: {distance_meters / 1000:.2f} km")

# Optional: Plot the route on a map
fig, ax = ox.plot_graph_route(G, shortest_path, route_linewidth=3, node_size=0)
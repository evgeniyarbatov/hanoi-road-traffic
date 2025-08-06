import osmnx as ox
import pandas as pd
import networkx as nx

# Path to your local OSM XML file
osm_file_path = "osm/hanoi-roads.osm"  # replace with your file

G = ox.graph_from_xml(
    osm_file_path,
    simplify=True
)

# Convert to undirected for betweenness centrality
G = G.to_undirected()

# Step 2: Compute edge betweenness centrality
edge_centrality = nx.edge_betweenness_centrality(G, weight="length", normalized=True)

# Step 3: Aggregate centrality by OSM way ID
way_centrality = {}

for u, v, k, data in G.edges(keys=True, data=True):
    osmid = data.get("osmid")
    cent = edge_centrality.get((u, v, k), 0.0)

    if isinstance(osmid, list):
        for wid in osmid:
            way_centrality[wid] = way_centrality.get(wid, 0.0) + cent
    elif osmid is not None:
        way_centrality[osmid] = way_centrality.get(osmid, 0.0) + cent

# Step 4: Write to CSV
df = pd.DataFrame(way_centrality.items(), columns=["way_id", "centrality"])
df.sort_values("centrality", ascending=False, inplace=True)
df.to_csv("data/centrality.csv", index=False)

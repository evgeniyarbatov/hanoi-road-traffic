import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
from collections import defaultdict


def parse_osm_file(osm_file):
    tree = ET.parse(osm_file)
    root = tree.getroot()

    ways = []
    for way in root.findall("way"):
        tags = {tag.get("k"): tag.get("v") for tag in way.findall("tag")}
        if "highway" not in tags:
            continue

        nodes = [int(nd.get("ref")) for nd in way.findall("nd")]
        ways.append({"id": int(way.get("id")), "nodes": nodes, "tags": tags})

    return ways


def calculate_node_degrees(ways):
    connections = defaultdict(set)
    for way in ways:
        for i, node in enumerate(way["nodes"]):
            if i > 0:
                connections[node].add(way["nodes"][i - 1])
            if i < len(way["nodes"]) - 1:
                connections[node].add(way["nodes"][i + 1])
    return {node: len(neigh) for node, neigh in connections.items()}


def get_highway_importance_weight(highway):
    weights = {
        "motorway": 10,
        "trunk": 9,
        "primary": 8,
        "secondary": 6,
        "tertiary": 4,
        "residential": 2,
        "unclassified": 1,
        "service": 0.5,
        "footway": 0.1,
        "cycleway": 0.1,
        "path": 0.1,
    }
    return weights.get(highway, 1)


def calculate_way_metrics(ways, node_degrees):
    metrics = []
    for way in ways:
        nodes = way["nodes"]
        tags = way["tags"]
        degrees = [node_degrees.get(n, 0) for n in nodes]

        total_intersections = sum(d > 2 for d in degrees)
        major_intersections = sum(d > 3 for d in degrees)
        max_degree = max(degrees, default=0)
        avg_degree = np.mean(degrees) if degrees else 0
        intersection_density = total_intersections / len(nodes) if nodes else 0
        weight = get_highway_importance_weight(tags.get("highway", ""))

        score = (
            total_intersections * 1.0
            + major_intersections * 2.0
            + max_degree * 0.5
            + avg_degree * 0.3
            + weight * 0.2
        )

        metrics.append(
            {
                "way_id": way["id"],
                "highway_type": tags.get("highway", "unknown"),
                "name": tags.get("name", "unnamed"),
                "total_nodes": len(nodes),
                "total_intersections": total_intersections,
                "major_intersections": major_intersections,
                "max_node_degree": max_degree,
                "avg_node_degree": round(avg_degree, 2),
                "intersection_density": round(intersection_density, 3),
                "importance_weight": weight,
                "intersection_score": round(score, 2),
                "lanes": tags.get("lanes"),
                "maxspeed": tags.get("maxspeed"),
            }
        )
    return pd.DataFrame(metrics)


def export_way_metrics(osm_file, output_file="way_metrics.csv"):
    ways = parse_osm_file(osm_file)
    node_degrees = calculate_node_degrees(ways)
    metrics_df = calculate_way_metrics(ways, node_degrees)
    metrics_df.to_csv(output_file, index=False)
    print(f"Saved way metrics to {output_file}")


# Example usage
if __name__ == "__main__":
    osm_file = "osm/hanoi-roads.osm"  # Replace with your actual file
    export_way_metrics(osm_file, output_file="data/metrics.csv")

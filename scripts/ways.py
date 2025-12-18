import osmium
import csv
import argparse
from shapely.geometry import LineString


class WayHandler(osmium.SimpleHandler):
    def __init__(self):
        super(WayHandler, self).__init__()
        self.way_midpoints = []

    def way(self, w):
        try:
            coords = [(n.lon, n.lat) for n in w.nodes]
            if len(coords) >= 2:
                line = LineString(coords)
                midpoint = line.interpolate(0.5, normalized=True)
                lat, lon = float(midpoint.y), float(midpoint.x)
                self.way_midpoints.append((w.id, lat, lon))
        except Exception as e:
            print("Error processing way:", e)


def write_midpoints_to_csv(way_midpoints, filename):
    with open(filename, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["way_id", "lat", "lon"])  # updated header

        for way_id, lat, lon in way_midpoints:
            writer.writerow([way_id, lat, lon])


def main():
    parser = argparse.ArgumentParser(description="Extract OSM way midpoints to CSV")
    parser.add_argument("osm_file", help="Input OSM file (e.g., map.osm)")
    parser.add_argument("csv_file", help="Output CSV file (e.g., midpoints.csv)")
    args = parser.parse_args()

    handler = WayHandler()
    print(f"Processing OSM file: {args.osm_file}")
    handler.apply_file(args.osm_file, locations=True)

    print(f"Total ways processed: {len(handler.way_midpoints)}")
    print(f"Writing midpoints to CSV: {args.csv_file}")
    write_midpoints_to_csv(handler.way_midpoints, args.csv_file)


if __name__ == "__main__":
    main()

import osmium
import csv
import argparse

class WayHandler(osmium.SimpleHandler):
    def __init__(self):
        super(WayHandler, self).__init__()
        self.ways = []

    def way(self, w):
        try:
            coords = [(n.lon, n.lat) for n in w.nodes]
            if len(coords) >= 2:
                self.ways.append((w.id, coords))  # store way ID with coords
        except Exception as e:
            print("Error processing way:", e)

def write_ways_to_csv(ways, filename):
    with open(filename, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['way_id', 'coordinates'])  # header

        for way_id, coords in ways:
            coord_str = ';'.join(f"{lon},{lat}" for lon, lat in coords)
            writer.writerow([way_id, coord_str])

def main():
    parser = argparse.ArgumentParser(description="Extract OSM ways to CSV")
    parser.add_argument("osm_file", help="Input OSM file (e.g., map.osm)")
    parser.add_argument("csv_file", help="Output CSV file (e.g., ways.csv)")
    args = parser.parse_args()

    handler = WayHandler()
    print(f"Processing OSM file: {args.osm_file}")
    handler.apply_file(args.osm_file, locations=True)

    print(f"Writing {len(handler.ways)} ways to CSV: {args.csv_file}")
    write_ways_to_csv(handler.ways, args.csv_file)

if __name__ == "__main__":
    main()

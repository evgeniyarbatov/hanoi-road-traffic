import psycopg2
import csv
import json

DB_CONFIG = {
    "host": "localhost",
    "database": "traffic",
    "user": "traffic",
    "password": "DKW9b9agY23e",
    "port": 5432,
}

# SQL query
QUERY = """
SELECT
    timestamp,
    lat,
    lon,
    ST_AsText(
        ST_SetSRID(
            ST_GeomFromWKB(decode(segment, 'hex')),
            4326
        )
    ) AS segment,
    (data->'flowSegmentData'->>'currentSpeed')::numeric AS current_speed,
    (data->'flowSegmentData'->>'freeFlowSpeed')::numeric AS free_flow_speed,
    (data->'flowSegmentData'->>'currentTravelTime')::numeric AS current_travel_time,
    (data->'flowSegmentData'->>'freeFlowTravelTime')::numeric AS free_flow_travel_time
FROM traffic;
"""

# Output CSV file
OUTPUT_CSV = "data/traffic.csv"


def parse_linestring(linestring):
    """
    Convert a WKT LINESTRING into a list of [lat, lon] pairs.
    Example input: "LINESTRING(30.1234 50.5678, 30.2234 50.6678)"
    """
    # Remove the "LINESTRING(" prefix and trailing ")"
    coords_str = linestring.strip().replace("LINESTRING(", "").replace(")", "")

    # Split by comma, then split each pair by space
    coords = []
    for point in coords_str.split(","):
        lon_str, lat_str = point.strip().split()
        coords.append([float(lat_str), float(lon_str)])

    return coords


def fetch_and_save():
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Run the query
        cur.execute(QUERY)
        rows = cur.fetchall()

        # Get column names
        col_names = [desc[0] for desc in cur.description]

        # Find the index of the 'segment' column
        segment_idx = col_names.index("segment")

        # Convert segment to JSON list
        processed_rows = []
        for row in rows:
            row = list(row)
            row[segment_idx] = json.dumps(parse_linestring(row[segment_idx]))
            processed_rows.append(row)

        # Write to CSV
        with open(OUTPUT_CSV, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(col_names)
            writer.writerows(processed_rows)

        print(f"✅ Data saved to {OUTPUT_CSV}")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if "cur" in locals():
            cur.close()
        if "conn" in locals():
            conn.close()


if __name__ == "__main__":
    fetch_and_save()

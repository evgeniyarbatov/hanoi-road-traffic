import psycopg2
import csv
import gzip

# --- Configuration ---
DB_NAME = "traffic"
DB_USER = "traffic"
DB_PASS = "DKW9b9agY23e"
DB_HOST = "localhost"
DB_PORT = "5432"

OUTPUT_FILE = "postgis/traffic.csv.gz"

# --- Connect to the database ---
conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
    port=DB_PORT
)
cur = conn.cursor()

# Export query: Convert geometry to WKT for portability
cur.execute("""
    SELECT
        id,
        timestamp,
        lat,
        lon,
        ST_AsText(querypoint) AS querypoint_wkt,
        ST_AsText(segment) AS segment_wkt,
        data::text
    FROM traffic
    ORDER BY id
""")

# --- Write CSV and compress ---
with gzip.open(OUTPUT_FILE, 'wt', newline='', encoding='utf-8') as gzfile:
    writer = csv.writer(gzfile)
    # Write header
    col_names = [desc[0] for desc in cur.description]
    writer.writerow(col_names)
    # Write rows
    for row in cur:
        writer.writerow(row)

cur.close()
conn.close()

print(f"✅ Dump complete: {OUTPUT_FILE}")

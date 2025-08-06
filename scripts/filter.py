import sys
import requests

import pandas as pd

from geopy.distance import geodesic

def min_distance(df):
    distances = [None]  # First point has no previous point

    for idx in range(1, len(df)):
        print(idx)
        current_point = (df.iloc[idx]['lat'], df.iloc[idx]['lon'])
        min_distance = float('inf')

        for prev_idx in range(idx):
            prev_point = (df.iloc[prev_idx]['lat'], df.iloc[prev_idx]['lon'])
            distance = geodesic(current_point, prev_point).meters
            if distance < min_distance:
                min_distance = distance

        distances.append(min_distance)

    df['min_distance'] = distances
    return df

def osrm_format(coords):
    lat, lon = coords
    return f"{lon},{lat}"

def get_distance(start, stop):    
    points = [start] + [stop]
    points = ';'.join(map(osrm_format, points))

    response = requests.get(
        f"http://127.0.0.1:6000/route/v1/foot/{points}", 
        params = {
            'geometries': 'polyline6',
            'overview': 'full',
        },
    )
    routes = response.json()
    
    if routes['code'] != 'Ok':
        return None
    
    return float(routes['routes'][0]['distance'])

def main(
    start_lat,
    start_lon,
    filename,
):
    start = (float(start_lat), float(start_lon))
    
    df = pd.read_csv(filename)
    
    df = min_distance(df)
        
    df['distance'] = df.apply(
        lambda row: get_distance(
            start,
            (row['lat'], row['lon']),
        ),
        axis=1
    )
    
    df.to_csv(filename, index=False)

if __name__ == "__main__":
    main(*sys.argv[1:])
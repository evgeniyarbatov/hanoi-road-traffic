import sys

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

def main(
    filename,
):
    df = pd.read_csv(filename)
    df = min_distance(df)
    df.to_csv(filename, index=False)

if __name__ == "__main__":
    main(*sys.argv[1:])
import pandas as pd
import ast
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import contextily as ctx
from shapely.geometry import LineString
import geopandas as gpd

# ===== Step 1: Load CSV =====
df = pd.read_csv("data/traffic.csv")

# Convert timestamp to datetime
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Parse 'segment' from string to Python list
df['segment'] = df['segment'].apply(lambda x: ast.literal_eval(x))

# ===== Step 2: Expand into GeoDataFrame =====
def segment_to_linestring(segment):
    return LineString([(lon, lat) for lat, lon in segment])

df['geometry'] = df['segment'].apply(segment_to_linestring)

gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")
gdf = gdf.to_crs(epsg=3857)  # Web Mercator for OSM tiles

# ===== Step 3: Animation Setup =====
timestamps = sorted(gdf['timestamp'].unique())

fig, ax = plt.subplots(figsize=(10, 10))
ax.set_axis_off()

def get_color(speed, free_speed):
    ratio = speed / free_speed
    if ratio >= 0.8:
        return "green"
    elif ratio >= 0.5:
        return "orange"
    else:
        return "red"

def get_linewidth(speed, free_speed, min_width=2, max_width=8):
    # Avoid division by zero
    if free_speed <= 0:
        return min_width
    ratio = max(0, 1 - (speed / free_speed))  # 0 = no congestion, 1 = fully stopped
    return min_width + ratio * (max_width - min_width)

# Precompute bounding box for all segments
xmin, ymin, xmax, ymax = gdf.total_bounds

fig, ax = plt.subplots(figsize=(12, 12))
fig.patch.set_alpha(0)  # transparent figure background
ax.set_facecolor("none")  # transparent axes background
ax.set_axis_off()

def update(frame):
    ax.clear()
    ax.set_axis_off()

    # Lock to bounding box to avoid shifting & white space
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)

    t = timestamps[frame]
    subset = gdf[gdf['timestamp'] == t]

    # Draw traffic segments
    for _, row in subset.iterrows():
        color = get_color(row['current_speed'], row['free_flow_speed'])
        lw = get_linewidth(row['current_speed'], row['free_flow_speed'])
        ax.plot(*row['geometry'].coords.xy, color=color, linewidth=lw)
        
    # Add OSM basemap without attribution
    ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, attribution=False)

    # Timestamp inside bottom-left
    ax.text(
        0.02, 0.02,
        f"{t:%Y-%m-%d %H:%M:%S}",
        transform=ax.transAxes,
        fontsize=12,
        color="black",
        bbox=dict(facecolor="white", alpha=0.6, edgecolor="none", pad=2)
    )

    ax.text(
        0.5, 0.98,  # x=center, y=near top (axes coords)
        "Green = Free flow | Orange = Moderate traffic | Red = Heavy congestion",
        transform=ax.transAxes,
        fontsize=12,
        ha="center",
        va="top",
        color="black",
        bbox=dict(facecolor="white", alpha=0.6, edgecolor="none", pad=2)
    )

ani = FuncAnimation(fig, update, frames=len(timestamps), interval=1000, repeat=True)

# Save GIF with high DPI and no borders
ani.save(
    "data/traffic.gif",
    writer="pillow",
    dpi=200,
    savefig_kwargs={
        'bbox_inches': 'tight', 
        'pad_inches': 0,
        'transparent': True,
    }
)

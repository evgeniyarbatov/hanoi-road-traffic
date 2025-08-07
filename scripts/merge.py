import pandas as pd

# Load all CSV files
distance_df = pd.read_csv("data/distance.csv")
metrics_df = pd.read_csv("data/metrics.csv")
score_df = pd.read_csv("data/score.csv")

# Initial row counts
print(f"distance.csv:   {len(distance_df)} rows")
print(f"metrics.csv:    {len(metrics_df)} rows")
print(f"score.csv:      {len(score_df)} rows")

# Rename osmid to way_id in score_df for consistent merging
score_df = score_df.rename(columns={"osmid": "way_id"})

# Check unique way_ids
print(f"Unique way_ids in distance:   {distance_df['way_id'].nunique()}")
print(f"Unique way_ids in metrics:    {metrics_df['way_id'].nunique()}")
print(f"Unique way_ids in score:      {score_df['way_id'].nunique()}")

# Merge only distance, metrics, and score (excluding centrality)
merged_df = distance_df.merge(metrics_df, on="way_id", how="inner")
print(f"After merging distance + metrics: {len(merged_df)} rows")

merged_df = merged_df.merge(score_df, on="way_id", how="inner")
print(f"After merging with score:         {len(merged_df)} rows")

# Drop duplicate columns if any
merged_df = merged_df.loc[:, ~merged_df.columns.duplicated()]

# Save to a new CSV
merged_df.to_csv("data/merged.csv", index=False)
print("Merged CSV saved as: data/merged.csv")

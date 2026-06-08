import json
from pathlib import Path

import pandas as pd
from sklearn.neighbors import NearestNeighbors

from recommender import ContentBasedRecommender


BASE_DIR = Path(__file__).resolve().parent

def get_default_path(filename: str) -> Path:
    path_inside = BASE_DIR / "data" / filename
    if path_inside.exists():
        return path_inside
    return BASE_DIR.parent / "data" / filename


DATASET_PATH = get_default_path("dataset.csv")
OUTPUT_PATH = get_default_path("dataset_with_recommendations.csv")
N_RECOMMENDATIONS = 5


print("=" * 70)
print("MUSIC RECOMMENDER - CONTENT-BASED OFFLINE PROCESSING")
print("=" * 70)

print("\n[1] Loading and cleaning dataset...")
recommender = ContentBasedRecommender(DATASET_PATH)
df_dataset = recommender.df.reset_index(drop=True)
print(f"    - Tracks loaded: {len(df_dataset)}")
print(f"    - Genres: {df_dataset['genre'].nunique()}")
print(f"    - Artists: {df_dataset['artist'].nunique()}")

print("\n[2] Building nearest-neighbor index...")
neighbor_model = NearestNeighbors(
    n_neighbors=N_RECOMMENDATIONS + 1,
    metric="cosine",
    algorithm="brute",
)
neighbor_model.fit(recommender.feature_matrix)

print("\n[3] Finding similar tracks...")
distances, indices = neighbor_model.kneighbors(recommender.feature_matrix)

results = []
for row_index, row in df_dataset.iterrows():
    recommendations = {}

    for distance, candidate_index in zip(distances[row_index], indices[row_index]):
        if candidate_index == row_index:
            continue

        candidate = df_dataset.iloc[candidate_index]
        similarity = 1.0 - float(distance)

        if row["genre"] == candidate["genre"]:
            similarity += 0.05

        recommendations[candidate["track_id"]] = round(min(similarity, 1.0), 6)

        if len(recommendations) >= N_RECOMMENDATIONS:
            break

    results.append(
        {
            "track_id": row["track_id"],
            "track_name": row["track_name"],
            "artists": row["artist"],
            "popularity": row["popularity"],
            "duration_ms": row["duration_ms"],
            "track_genre": row["genre"],
            "num_recommendations": len(recommendations),
            "recommended_tracks": json.dumps(recommendations, ensure_ascii=False),
        }
    )

    if (row_index + 1) % 5000 == 0:
        print(f"    - Processed {row_index + 1}/{len(df_dataset)} tracks")

print("\n[4] Saving output...")
results_df = pd.DataFrame(results)
results_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")

successful_recs = results_df[results_df["num_recommendations"] > 0].shape[0]
print("\n[5] Done")
print(f"    - Total records: {len(results_df)}")
print(f"    - Tracks with recommendations: {successful_recs}/{len(results_df)}")
print(f"    - Average recommendations per track: {results_df['num_recommendations'].mean():.2f}")
print(f"    - Output file: {OUTPUT_PATH}")

print("\n[6] Preview")
print(results_df[["track_id", "track_name", "num_recommendations", "recommended_tracks"]].head(10))

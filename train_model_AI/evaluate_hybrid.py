from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import numpy as np
import pandas as pd

from recommender import ContentBasedRecommender


BASE_DIR = Path(__file__).resolve().parent

def get_default_path(filename: str) -> Path:
    path_inside = BASE_DIR / "data" / filename
    if path_inside.exists():
        return path_inside
    return BASE_DIR.parent / "data" / filename


DEFAULT_DATASET_PATH = get_default_path("dataset.csv")
DEFAULT_INTERACTIONS_PATH = get_default_path("lastfm_user_artist_interactions.csv")
DEFAULT_OUTPUT_PATH = get_default_path("hybrid_evaluation_summary.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate and compare different recommendation models on Last.fm data.",
    )
    parser.add_argument("--dataset-path", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--interactions-path", type=Path, default=DEFAULT_INTERACTIONS_PATH)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--max-users", type=int, default=1000)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def dcg_at_k(relevance: list[int]) -> float:
    return sum(rel / math.log2(index + 2) for index, rel in enumerate(relevance))


def evaluate_user_for_model(
    recommender: ContentBasedRecommender,
    user_id: str,
    train_interactions: list[dict[str, any]],
    train_artists: set[str],
    test_artists: set[str],
    top_n: int,
    model_type: str,
) -> dict[str, float | int] | None:
    recommendations = []

    if model_type == "popular":
        # Popularity baseline
        recommendations = recommender.get_popular(top_n=top_n)

    elif model_type == "content_based":
        # Content-based baseline (no CF)
        user_profile = recommender._build_user_profile(train_interactions)
        if user_profile is not None:
            normalized_profile = recommender._normalize_vector(user_profile)
            similarity_scores = recommender.normalized_feature_matrix @ normalized_profile
            final_scores = similarity_scores + (recommender.popularity_score * 0.03)
            
            seen_track_ids = set()
            for candidate_idx in recommender._rank_indices(final_scores, top_n=top_n, pool_multiplier=220):
                candidate_artists = recommender.track_artist_tokens[candidate_idx]
                # Exclude train artists to make it fair
                if candidate_artists & train_artists:
                    continue
                candidate = recommender.df.iloc[candidate_idx]
                if candidate["track_id"] in seen_track_ids:
                    continue
                seen_track_ids.add(candidate["track_id"])
                
                recommendations.append(
                    recommender._build_recommendation_payload(
                        candidate=candidate,
                        score=float(final_scores[candidate_idx]),
                        reference_song=None,
                    )
                )
                if len(recommendations) >= top_n:
                    break

    elif model_type == "collaborative":
        # Collaborative filtering baseline (no content similarity)
        artist_scores = recommender._score_candidate_artists_from_neighbors(
            interactions=train_interactions,
            excluded_artists=train_artists,
            source_user_id=user_id,
        )
        if artist_scores:
            ranked_artists = sorted(
                artist_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            used_track_ids = set()
            used_primary_artists = set()
            for artist, artist_score in ranked_artists[:top_n * 5]:
                if artist in used_primary_artists:
                    continue
                candidate_indices = recommender.artist_to_indices.get(artist, [])
                
                best_idx = None
                best_pop = -1
                for candidate_idx in candidate_indices:
                    candidate = recommender.df.iloc[candidate_idx]
                    if candidate["track_id"] in used_track_ids:
                        continue
                    pop = int(candidate["popularity"]) if pd.notna(candidate["popularity"]) else 0
                    if pop > best_pop:
                        best_pop = pop
                        best_idx = candidate_idx
                
                if best_idx is not None:
                    candidate = recommender.df.iloc[best_idx]
                    used_track_ids.add(candidate["track_id"])
                    used_primary_artists.add(artist)
                    recommendations.append(
                        recommender._build_recommendation_payload(
                            candidate=candidate,
                            score=float(artist_score),
                            reference_song=None,
                        )
                    )
                    if len(recommendations) >= top_n:
                        break

    elif model_type == "hybrid":
        # Hybrid recommender (TF-IDF + Content similarity + Genre)
        recommendations = recommender.recommend_from_artist_interactions(
            interactions=train_interactions,
            top_n=top_n,
            excluded_artists=train_artists,
            source_user_id=user_id,
        )

    if not recommendations:
        return None

    # Calculate metrics
    relevant_flags = []
    hit_test_artists = set()
    recommended_tracks = set()

    for recommendation in recommendations[:top_n]:
        track_id = recommendation["track_id"]
        recommended_tracks.add(track_id)
        track_index = recommender.track_index[track_id]
        matched_test_artists = recommender.track_artist_tokens[track_index] & test_artists
        is_relevant = bool(matched_test_artists)
        relevant_flags.append(1 if is_relevant else 0)
        hit_test_artists.update(matched_test_artists)

    while len(relevant_flags) < top_n:
        relevant_flags.append(0)

    relevant_count = sum(relevant_flags)
    ideal_relevance = [1] * min(len(test_artists), top_n)
    ideal_dcg = dcg_at_k(ideal_relevance)

    return {
        "precision": relevant_count / top_n,
        "recall": len(hit_test_artists) / len(test_artists) if len(test_artists) > 0 else 0.0,
        "hit_rate": 1 if relevant_count > 0 else 0,
        "ndcg": dcg_at_k(relevant_flags) / ideal_dcg if ideal_dcg else 0.0,
        "unique_tracks": len(recommended_tracks),
    }


def evaluate(args: argparse.Namespace) -> dict[str, any]:
    print("=" * 70)
    print("MUSIC RECOMMENDER BENCHMARK EVALUATION")
    print("=" * 70)

    recommender = ContentBasedRecommender(args.dataset_path, args.interactions_path)
    recommender._ensure_user_interactions_loaded()
    user_ids = list((recommender.user_interactions or {}).keys())[: args.max_users]
    rng = random.Random(args.seed)

    print(f"\n[1] Evaluating {len(user_ids)} users with top-{args.top_n} recommendations...")

    models = ["popular", "content_based", "collaborative", "hybrid"]
    metrics_by_model = {model: [] for model in models}
    unique_tracks_by_model = {model: set() for model in models}

    evaluated_users_count = 0

    for index, user_id in enumerate(user_ids, start=1):
        interactions = recommender.get_user_interactions(user_id)
        artist_names = {
            interaction["normalized_artist"]
            for interaction in interactions
            if interaction.get("normalized_artist")
        }

        if len(artist_names) < 5:
            continue

        test_size = max(1, int(round(len(artist_names) * args.test_ratio)))
        shuffled_artists = list(artist_names)
        rng.shuffle(shuffled_artists)
        test_artists = set(shuffled_artists[:test_size])
        train_artists = set(shuffled_artists[test_size:])

        train_interactions = [
            interaction
            for interaction in interactions
            if interaction.get("normalized_artist") in train_artists
        ]

        if not train_interactions:
            continue

        user_has_results = False
        # Evaluate this user on all models
        for model in models:
            res = evaluate_user_for_model(
                recommender=recommender,
                user_id=user_id,
                train_interactions=train_interactions,
                train_artists=train_artists,
                test_artists=test_artists,
                top_n=args.top_n,
                model_type=model,
            )
            if res:
                metrics_by_model[model].append(res)
                user_has_results = True

        if user_has_results:
            evaluated_users_count += 1

        if index % 100 == 0:
            print(f"    - Processed {index}/{len(user_ids)} users")

    if evaluated_users_count == 0:
        raise RuntimeError("No users could be evaluated.")

    # Aggregate results
    summary = {
        "dataset_path": str(args.dataset_path),
        "interactions_path": str(args.interactions_path),
        "evaluated_users": evaluated_users_count,
        "top_n": args.top_n,
        "test_ratio": args.test_ratio,
        "results": {}
    }

    print("\n" + "=" * 70)
    print(f"EVALUATION SUMMARY TABLE (Top-{args.top_n})")
    print("=" * 70)
    print(f"{'Model':<20} | {'Precision':<9} | {'Recall':<9} | {'Hit Rate':<9} | {'NDCG':<9}")
    print("-" * 70)

    for model in models:
        results_list = metrics_by_model[model]
        if not results_list:
            continue
        
        precision = round(float(np.mean([row["precision"] for row in results_list])), 6)
        recall = round(float(np.mean([row["recall"] for row in results_list])), 6)
        hit_rate = round(float(np.mean([row["hit_rate"] for row in results_list])), 6)
        ndcg = round(float(np.mean([row["ndcg"] for row in results_list])), 6)
        
        summary["results"][model] = {
            "precision": precision,
            "recall": recall,
            "hit_rate": hit_rate,
            "ndcg": ndcg,
        }
        
        print(f"{model:<20} | {precision:<9.4f} | {recall:<9.4f} | {hit_rate:<9.4f} | {ndcg:<9.4f}")

    print("=" * 70)

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    with args.output_path.open("w", encoding="utf-8") as output_file:
        json.dump(summary, output_file, ensure_ascii=False, indent=2)

    print(f"Results saved to: {args.output_path}")
    return summary


if __name__ == "__main__":
    evaluate(parse_args())

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


def normalize_artist(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


class ContentBasedRecommender:
    DATASET_COLUMNS = [
        "index",
        "track_id",
        "artists",
        "album_name",
        "track_name",
        "popularity",
        "duration_ms",
        "explicit",
        "danceability",
        "energy",
        "key",
        "loudness",
        "mode",
        "speechiness",
        "acousticness",
        "instrumentalness",
        "liveness",
        "valence",
        "tempo",
        "time_signature",
        "track_genre",
    ]

    FEATURE_COLUMNS = [
        "popularity",
        "duration_ms",
        "danceability",
        "energy",
        "key",
        "loudness",
        "mode",
        "speechiness",
        "acousticness",
        "instrumentalness",
        "liveness",
        "valence",
        "tempo",
        "time_signature",
    ]

    def __init__(
        self,
        dataset_path: str | Path,
        user_interactions_path: str | Path | None = None,
    ) -> None:
        self.dataset_path = Path(dataset_path)
        self.user_interactions_path = Path(user_interactions_path) if user_interactions_path else None
        self.user_interactions: dict[str, list[dict[str, Any]]] | None = None
        self.user_artist_weights: dict[str, dict[str, float]] | None = None
        self.artist_user_weights: dict[str, list[tuple[str, float]]] | None = None
        self.user_weight_norms: dict[str, float] | None = None
        self.user_feedback: dict[str, dict[str, int]] = {}
        self.artist_idf: dict[str, float] = {}

        self.df = self._load_dataset()
        self.feature_columns = list(self.FEATURE_COLUMNS)
        self.track_count = len(self.df)
        self._build_feature_matrix()
        self._build_artist_index()
        self.popular_df = self.df.sort_values(
            by=["popularity", "track_name"],
            ascending=[False, True],
        ).reset_index(drop=True)

    def _load_dataset(self) -> pd.DataFrame:
        rows = []
        with self.dataset_path.open("r", encoding="utf-8") as dataset_file:
            reader = csv.reader(dataset_file)
            next(reader, None)  # Skip malformed header from the provided dataset.
            for raw_row in reader:
                normalized_row = self._normalize_row(raw_row)
                if normalized_row is None:
                    continue
                rows.append(normalized_row)

        df = pd.DataFrame(rows, columns=self.DATASET_COLUMNS)

        rename_map = {
            "artists": "artist",
            "album_name": "album",
            "track_genre": "genre",
        }
        df = df.rename(columns=rename_map)

        required_columns = {"track_id", "track_name", "artist", "album", "genre"}
        missing = required_columns - set(df.columns)
        if missing:
            raise ValueError(f"Dataset missing required columns: {sorted(missing)}")

        for column in self.FEATURE_COLUMNS:
            if column not in df.columns:
                df[column] = 0.0
            df[column] = pd.to_numeric(df[column], errors="coerce")

        if "explicit" in df.columns:
            df["explicit"] = (
                df["explicit"]
                .astype(str)
                .str.strip()
                .str.lower()
                .map({"true": 1, "false": 0})
                .fillna(0)
            )

        df[self.FEATURE_COLUMNS] = df[self.FEATURE_COLUMNS].fillna(df[self.FEATURE_COLUMNS].median())
        df["track_name"] = df["track_name"].fillna("").astype(str).str.strip()
        df["artist"] = df["artist"].fillna("").astype(str).str.strip()
        df["album"] = df["album"].fillna("").astype(str).str.strip()
        df["genre"] = df["genre"].fillna("unknown").astype(str).str.strip()

        return df.dropna(subset=["track_id"]).drop_duplicates(subset=["track_id"]).reset_index(drop=True)

    def _normalize_row(self, raw_row: list[str]) -> list[str] | None:
        if len(raw_row) == len(self.DATASET_COLUMNS):
            return raw_row

        if len(raw_row) == len(self.DATASET_COLUMNS) + 1 and raw_row[15] == "":
            fixed_row = raw_row[:15] + [raw_row[16].replace("danceability", "")] + raw_row[17:]
            return fixed_row if len(fixed_row) == len(self.DATASET_COLUMNS) else None

        return None

    def _build_feature_matrix(self) -> None:
        feature_frame = self.df[self.FEATURE_COLUMNS].copy()
        scaler = StandardScaler()
        audio_features_scaled = scaler.fit_transform(feature_frame)

        # Encode genre as one-hot and concatenate it
        genre_dummies = pd.get_dummies(self.df["genre"], prefix="genre")
        genre_features = genre_dummies.astype(float).to_numpy()
        genre_features_weighted = genre_features * 0.35

        self.feature_matrix = np.hstack([audio_features_scaled, genre_features_weighted])
        self.normalized_feature_matrix = self._normalize_matrix(self.feature_matrix)
        self.track_index = {
            track_id: index for index, track_id in enumerate(self.df["track_id"].tolist())
        }

        popularity = self.df["popularity"].fillna(0).astype(float).to_numpy()
        popularity_range = popularity.max() - popularity.min()
        self.popularity_score = (
            (popularity - popularity.min()) / popularity_range
            if popularity_range
            else np.zeros_like(popularity)
        )

    def _build_artist_index(self) -> None:
        self.track_artist_tokens: list[set[str]] = []
        self.artist_to_indices: dict[str, list[int]] = {}

        for index, artists in enumerate(self.df["artist"].tolist()):
            artist_tokens = {
                normalized_artist
                for artist in str(artists).split(";")
                if (normalized_artist := normalize_artist(artist))
            }
            self.track_artist_tokens.append(artist_tokens)

            for artist_token in artist_tokens:
                self.artist_to_indices.setdefault(artist_token, []).append(index)

        self.artist_feature_profiles = {
            artist: self.feature_matrix[indices].mean(axis=0)
            for artist, indices in self.artist_to_indices.items()
        }

    def _normalize_matrix(self, matrix: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def recommend_by_track(self, track_id: str, top_n: int = 10) -> list[dict[str, Any]]:
        idx = self.track_index.get(track_id)
        if idx is None:
            return []

        source_song = self.df.iloc[idx]
        similarity_scores = self.normalized_feature_matrix @ self.normalized_feature_matrix[idx]
        final_scores = self._apply_track_ranking_adjustments(
            source_index=idx,
            similarity_scores=similarity_scores,
        )

        recommendations = []
        for candidate_idx in self._rank_indices(final_scores, top_n=top_n, pool_multiplier=80):
            if candidate_idx == idx:
                continue

            candidate = self.df.iloc[candidate_idx]
            recommendations.append(
                self._build_recommendation_payload(
                    candidate=candidate,
                    score=float(final_scores[candidate_idx]),
                    reference_song=source_song,
                )
            )

            if len(recommendations) >= top_n:
                break

        return recommendations

    def recommend_by_user(
        self,
        user_id: str,
        top_n: int = 10,
        exclude_known_artists: bool = True,
    ) -> list[dict[str, Any]]:
        interactions = self.get_user_interactions(user_id)
        if not interactions:
            return []

        excluded_artists = {
            interaction["normalized_artist"]
            for interaction in interactions
            if interaction.get("normalized_artist")
        } if exclude_known_artists else set()

        return self.recommend_from_artist_interactions(
            interactions=interactions,
            top_n=top_n,
            excluded_artists=excluded_artists,
            source_user_id=user_id,
        )

    def recommend_blend(
        self,
        user_id_1: str,
        user_id_2: str,
        top_n: int = 10,
    ) -> dict[str, Any]:
        interactions_1 = self.get_user_interactions(user_id_1)
        interactions_2 = self.get_user_interactions(user_id_2)

        profile_1 = self._build_user_profile(interactions_1, user_id_1)
        profile_2 = self._build_user_profile(interactions_2, user_id_2)

        if profile_1 is None:
            profile_1 = np.zeros(self.feature_matrix.shape[1])
        if profile_2 is None:
            profile_2 = np.zeros(self.feature_matrix.shape[1])

        norm_1 = np.linalg.norm(profile_1)
        norm_2 = np.linalg.norm(profile_2)
        if norm_1 > 0 and norm_2 > 0:
            match_score = float(np.dot(profile_1, profile_2) / (norm_1 * norm_2))
            match_score = max(0.0, min(1.0, (match_score + 1.0) / 2.0 if match_score < 0 else match_score))
        else:
            match_score = 0.5

        blend_vector = 0.5 * profile_1 + 0.5 * profile_2

        disliked_tracks = set()
        for uid in [user_id_1, user_id_2]:
            if uid and uid in self.user_feedback:
                disliked_tracks.update({tid for tid, val in self.user_feedback[uid].items() if val == -1})

        excluded_artists = set()
        for inters in [interactions_1, interactions_2]:
            for interaction in inters:
                if interaction.get("normalized_artist"):
                    excluded_artists.add(interaction["normalized_artist"])

        normalized_blend = self._normalize_vector(blend_vector)
        similarity_scores = self.normalized_feature_matrix @ normalized_blend
        final_scores = similarity_scores + (self.popularity_score * 0.03)

        recommendations = []
        seen_track_ids = set()
        seen_artist_tokens = set()

        for candidate_idx in self._rank_indices(final_scores, top_n=top_n, pool_multiplier=220):
            candidate = self.df.iloc[candidate_idx]
            if candidate["track_id"] in seen_track_ids or candidate["track_id"] in disliked_tracks:
                continue

            candidate_artists = self.track_artist_tokens[candidate_idx]
            if candidate_artists & seen_artist_tokens:
                continue

            candidate_feat = self.normalized_feature_matrix[candidate_idx]
            sim_1 = float(np.dot(candidate_feat, self._normalize_vector(profile_1))) if norm_1 > 0 else 0.0
            sim_2 = float(np.dot(candidate_feat, self._normalize_vector(profile_2))) if norm_2 > 0 else 0.0

            if sim_1 > 0.4 and sim_2 > 0.4:
                match_type = "BOTH"
                reason = "Matches both of your music tastes perfectly"
            elif sim_1 > sim_2 + 0.1:
                match_type = "USER1"
                reason = "Fits your personal music taste profile"
            else:
                match_type = "USER2"
                reason = "Aligned with your friend's music profile"

            seen_track_ids.add(candidate["track_id"])
            seen_artist_tokens.update(candidate_artists)

            recommendations.append(
                {
                    "track_id": candidate["track_id"],
                    "track_name": candidate["track_name"],
                    "artist": candidate["artist"],
                    "album": candidate["album"],
                    "genre": candidate["genre"],
                    "popularity": int(candidate["popularity"]),
                    "score": float(final_scores[candidate_idx]),
                    "reason": reason,
                    "matchType": match_type,
                }
            )

            if len(recommendations) >= top_n:
                break

        return {
            "match_score": match_score,
            "recommendations": recommendations,
        }

    def recommend_from_artist_interactions(
        self,
        interactions: list[dict[str, Any]],
        top_n: int = 10,
        excluded_artists: set[str] | None = None,
        source_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        excluded_artists = excluded_artists or set()
        collaborative_recommendations = self._recommend_with_artist_collaborative_filtering(
            interactions=interactions,
            top_n=top_n,
            excluded_artists=excluded_artists,
            source_user_id=source_user_id,
        )

        if len(collaborative_recommendations) >= top_n:
            return collaborative_recommendations

        user_profile = self._build_user_profile(interactions, source_user_id)
        if user_profile is None:
            return collaborative_recommendations

        normalized_profile = self._normalize_vector(user_profile)
        similarity_scores = self.normalized_feature_matrix @ normalized_profile
        final_scores = similarity_scores + (self.popularity_score * 0.03)

        recommendations = list(collaborative_recommendations)
        seen_track_ids = {
            recommendation["track_id"]
            for recommendation in recommendations
        }
        seen_artist_tokens = set()
        for recommendation in recommendations:
            track_index = self.track_index.get(recommendation["track_id"])
            if track_index is not None:
                seen_artist_tokens.update(self.track_artist_tokens[track_index])

        # Get disliked tracks to exclude
        disliked_tracks = set()
        if source_user_id and source_user_id in self.user_feedback:
            disliked_tracks = {tid for tid, val in self.user_feedback[source_user_id].items() if val == -1}

        for candidate_idx in self._rank_indices(final_scores, top_n=top_n, pool_multiplier=220):
            candidate_artists = self.track_artist_tokens[candidate_idx]
            if candidate_artists & excluded_artists:
                continue

            if candidate_artists & seen_artist_tokens:
                continue

            candidate = self.df.iloc[candidate_idx]
            if candidate["track_id"] in seen_track_ids:
                continue

            if candidate["track_id"] in disliked_tracks:
                continue

            recommendations.append(
                self._build_recommendation_payload(
                    candidate=candidate,
                    score=float(final_scores[candidate_idx]),
                    reference_song=None,
                    reason=self._build_user_reason(interactions, candidate),
                )
            )

            if len(recommendations) >= top_n:
                break

        return recommendations

    def get_user_interactions(self, user_id: str) -> list[dict[str, Any]]:
        self._ensure_user_interactions_loaded()
        if self.user_interactions is None:
            return []
        return list(self.user_interactions.get(user_id, []))

    def get_demo_users(self, limit: int = 12) -> list[dict[str, Any]]:
        self._ensure_user_interactions_loaded()
        if self.user_interactions is None:
            return []

        demo_users = []
        for user_id, interactions in self.user_interactions.items():
            demo_users.append(
                {
                    "user_id": user_id,
                    "interactions": len(interactions),
                    "top_artists": [
                        interaction["artist_name"]
                        for interaction in interactions[:5]
                    ],
                }
            )

            if len(demo_users) >= limit:
                break

        return demo_users

    def get_popular(self, top_n: int = 10) -> list[dict[str, Any]]:
        rows = self.popular_df.head(top_n)
        return [
            self._build_recommendation_payload(
                candidate=row,
                score=float(row["popularity"]) if pd.notna(row["popularity"]) else 0.0,
                reference_song=None,
                reason="Recommended because this track is currently popular",
            )
            for _, row in rows.iterrows()
        ]

    def _ensure_user_interactions_loaded(self) -> None:
        if self.user_interactions is not None:
            if self.user_artist_weights is None or self.artist_user_weights is None:
                self._build_user_interaction_indexes()
            return

        self.user_interactions = {}
        if self.user_interactions_path is None or not self.user_interactions_path.exists():
            self._build_user_interaction_indexes()
            return

        with self.user_interactions_path.open("r", encoding="utf-8", newline="") as interaction_file:
            reader = csv.DictReader(interaction_file)
            for row in reader:
                normalized_artist = row.get("normalized_artist", "")
                if normalized_artist not in self.artist_feature_profiles:
                    continue

                try:
                    weight = float(row.get("weight", "0"))
                    plays = int(row.get("plays", "0"))
                except ValueError:
                    continue

                self.user_interactions.setdefault(row["user_id"], []).append(
                    {
                        "artist_name": row.get("artist_name", ""),
                        "normalized_artist": normalized_artist,
                        "plays": plays,
                        "weight": weight,
                    }
                )

        # Calculate IDF for each artist based on self.user_interactions
        num_users = len(self.user_interactions)
        if num_users > 0:
            artist_dfs = {}
            for u_id, ints in self.user_interactions.items():
                seen_artists = {item["normalized_artist"] for item in ints if item.get("normalized_artist")}
                for a in seen_artists:
                    artist_dfs[a] = artist_dfs.get(a, 0) + 1

            for a, df in artist_dfs.items():
                self.artist_idf[a] = float(np.log((num_users + 1) / (df + 1)) + 1.0)

        self._build_user_interaction_indexes()

    def _build_user_interaction_indexes(self) -> None:
        self.user_artist_weights = {}
        self.artist_user_weights = {}
        self.user_weight_norms = {}

        if self.user_interactions is None:
            return

        for user_id, interactions in self.user_interactions.items():
            artist_weights: dict[str, float] = {}
            for interaction in interactions:
                normalized_artist = str(interaction.get("normalized_artist", ""))
                if not normalized_artist:
                    continue

                try:
                    plays = int(interaction.get("plays", 0))
                    tf = float(np.log1p(plays))
                    idf = self.artist_idf.get(normalized_artist, 1.0)
                    weight = tf * idf
                except (TypeError, ValueError):
                    continue

                if weight <= 0:
                    continue

                artist_weights[normalized_artist] = max(
                    artist_weights.get(normalized_artist, 0.0),
                    weight,
                )

            if not artist_weights:
                continue

            self.user_artist_weights[user_id] = artist_weights
            norm = float(np.linalg.norm(list(artist_weights.values())))
            self.user_weight_norms[user_id] = norm if norm else 1.0

            for artist, weight in artist_weights.items():
                self.artist_user_weights.setdefault(artist, []).append((user_id, weight))

        for postings in self.artist_user_weights.values():
            postings.sort(key=lambda user_weight: user_weight[1], reverse=True)

    def _recommend_with_artist_collaborative_filtering(
        self,
        interactions: list[dict[str, Any]],
        top_n: int,
        excluded_artists: set[str],
        source_user_id: str | None,
    ) -> list[dict[str, Any]]:
        artist_scores = self._score_candidate_artists_from_neighbors(
            interactions=interactions,
            excluded_artists=excluded_artists,
            source_user_id=source_user_id,
        )
        if not artist_scores:
            return []

        user_profile = self._build_user_profile(interactions, source_user_id)
        if user_profile is not None:
            content_scores = self.normalized_feature_matrix @ self._normalize_vector(user_profile)
        else:
            content_scores = np.zeros(self.track_count)

        max_artist_score = max(artist_scores.values()) or 1.0
        ranked_artists = sorted(
            artist_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        recommendations = []
        used_track_ids = set()
        used_primary_artists = set()
        candidate_artist_limit = max(top_n * 40, 120)

        # Get disliked tracks to exclude
        disliked_tracks = set()
        if source_user_id and source_user_id in self.user_feedback:
            disliked_tracks = {tid for tid, val in self.user_feedback[source_user_id].items() if val == -1}

        for artist, artist_score in ranked_artists[:candidate_artist_limit]:
            if artist in used_primary_artists:
                continue

            candidate_indices = self.artist_to_indices.get(artist, [])
            best_index = None
            best_score = -np.inf
            artist_component = artist_score / max_artist_score

            for candidate_idx in candidate_indices:
                candidate_artists = self.track_artist_tokens[candidate_idx]
                if candidate_artists & excluded_artists:
                    continue

                candidate = self.df.iloc[candidate_idx]
                if candidate["track_id"] in used_track_ids:
                    continue

                if candidate["track_id"] in disliked_tracks:
                    continue

                track_score = (
                    artist_component
                    + (float(content_scores[candidate_idx]) * 0.18)
                    + (float(self.popularity_score[candidate_idx]) * 0.08)
                )
                if track_score > best_score:
                    best_score = track_score
                    best_index = candidate_idx

            if best_index is None:
                continue

            candidate = self.df.iloc[best_index]
            used_track_ids.add(candidate["track_id"])
            used_primary_artists.add(artist)
            recommendations.append(
                self._build_recommendation_payload(
                    candidate=candidate,
                    score=float(best_score),
                    reference_song=None,
                    reason=self._build_collaborative_reason(interactions, candidate),
                )
            )

            if len(recommendations) >= top_n:
                break

        return recommendations

    def _score_candidate_artists_from_neighbors(
        self,
        interactions: list[dict[str, Any]],
        excluded_artists: set[str],
        source_user_id: str | None,
        max_seed_artists: int = 20,
        max_users_per_artist: int = 1800,
        max_neighbors: int = 350,
    ) -> dict[str, float]:
        self._ensure_user_interactions_loaded()
        if not self.user_artist_weights or not self.artist_user_weights or not self.user_weight_norms:
            return {}

        seed_weights: dict[str, float] = {}
        for interaction in interactions:
            normalized_artist = str(interaction.get("normalized_artist", ""))
            if normalized_artist not in self.artist_to_indices:
                continue

            try:
                weight = float(interaction.get("weight", 0.0))
            except (TypeError, ValueError):
                continue

            if weight <= 0:
                continue

            seed_weights[normalized_artist] = max(
                seed_weights.get(normalized_artist, 0.0),
                weight,
            )

        if not seed_weights:
            return {}

        target_norm = float(np.linalg.norm(list(seed_weights.values()))) or 1.0
        neighbor_scores: dict[str, float] = {}
        seed_artists = sorted(
            seed_weights.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:max_seed_artists]

        for artist, seed_weight in seed_artists:
            for neighbor_user_id, neighbor_weight in self.artist_user_weights.get(artist, [])[:max_users_per_artist]:
                if source_user_id and neighbor_user_id == source_user_id:
                    continue

                neighbor_scores[neighbor_user_id] = (
                    neighbor_scores.get(neighbor_user_id, 0.0)
                    + (seed_weight * neighbor_weight)
                )

        if not neighbor_scores:
            return {}

        ranked_neighbors = []
        for neighbor_user_id, raw_score in neighbor_scores.items():
            neighbor_norm = self.user_weight_norms.get(neighbor_user_id, 1.0)
            ranked_neighbors.append((
                neighbor_user_id,
                raw_score / (target_norm * neighbor_norm),
            ))

        ranked_neighbors.sort(key=lambda item: item[1], reverse=True)

        candidate_artist_scores: dict[str, float] = {}
        for neighbor_user_id, similarity in ranked_neighbors[:max_neighbors]:
            if similarity <= 0:
                continue

            for artist, artist_weight in self.user_artist_weights.get(neighbor_user_id, {}).items():
                if artist in seed_weights or artist in excluded_artists:
                    continue

                if artist not in self.artist_to_indices:
                    continue

                candidate_artist_scores[artist] = (
                    candidate_artist_scores.get(artist, 0.0)
                    + (similarity * artist_weight)
                )

        return candidate_artist_scores

    def _build_user_profile(self, interactions: list[dict[str, Any]], user_id: str | None = None) -> np.ndarray | None:
        weighted_profiles = []
        weights = []

        for interaction in interactions:
            normalized_artist = interaction.get("normalized_artist")
            artist_profile = self.artist_feature_profiles.get(str(normalized_artist))
            if artist_profile is None:
                continue

            weight = float(interaction.get("weight", 0.0))
            if weight <= 0:
                continue

            weighted_profiles.append(artist_profile * weight)
            weights.append(weight)

        base_profile = None
        if weighted_profiles:
            base_profile = np.sum(weighted_profiles, axis=0) / sum(weights)

        if user_id and user_id in self.user_feedback and self.user_feedback[user_id]:
            feedbacks = self.user_feedback[user_id]
            liked_tracks = [tid for tid, val in feedbacks.items() if val == 1]
            if liked_tracks:
                liked_vectors = []
                for tid in liked_tracks:
                    idx = self.track_index.get(tid)
                    if idx is not None:
                        liked_vectors.append(self.feature_matrix[idx])
                
                if liked_vectors:
                    liked_mean = np.mean(liked_vectors, axis=0)
                    if base_profile is not None:
                        base_profile = base_profile * 0.6 + liked_mean * 0.4
                    else:
                        base_profile = liked_mean

        return base_profile

    def add_user_feedback(self, user_id: str, track_id: str, feedback_type: str) -> None:
        if user_id not in self.user_feedback:
            self.user_feedback[user_id] = {}
        val = 1 if feedback_type.upper() == "LIKE" else -1
        self.user_feedback[user_id][track_id] = val

    def reset_user_feedback(self, user_id: str) -> None:
        if user_id in self.user_feedback:
            self.user_feedback[user_id] = {}

    def _apply_track_ranking_adjustments(
        self,
        source_index: int,
        similarity_scores: np.ndarray,
    ) -> np.ndarray:
        source_song = self.df.iloc[source_index]
        source_genre = source_song["genre"]
        source_artists = self.track_artist_tokens[source_index]

        final_scores = similarity_scores.copy()
        same_genre_mask = self.df["genre"].to_numpy() == source_genre
        final_scores[same_genre_mask] += 0.05
        final_scores += self.popularity_score * 0.02

        for candidate_idx, candidate_artists in enumerate(self.track_artist_tokens):
            if candidate_idx != source_index and source_artists & candidate_artists:
                final_scores[candidate_idx] -= 0.015

        final_scores[source_index] = -np.inf
        return final_scores

    def _rank_indices(
        self,
        scores: np.ndarray,
        top_n: int,
        pool_multiplier: int = 60,
    ) -> np.ndarray:
        if top_n <= 0:
            return np.array([], dtype=int)

        candidate_count = min(len(scores), max(top_n * pool_multiplier, top_n + 100))
        if candidate_count >= len(scores):
            return np.argsort(scores)[::-1]

        candidate_indices = np.argpartition(scores, -candidate_count)[-candidate_count:]
        return candidate_indices[np.argsort(scores[candidate_indices])[::-1]]

    def _build_recommendation_payload(
        self,
        candidate: pd.Series,
        score: float,
        reference_song: pd.Series | None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "track_id": candidate["track_id"],
            "track_name": candidate["track_name"],
            "artist": candidate["artist"],
            "album": candidate["album"],
            "genre": candidate["genre"],
            "popularity": int(candidate["popularity"]) if pd.notna(candidate["popularity"]) else 0,
            "score": round(score, 6),
            "reason": reason or self._build_track_reason(reference_song, candidate),
        }

    def _build_track_reason(self, reference_song: pd.Series | None, candidate: pd.Series) -> str:
        if reference_song is None:
            return "Recommended because this track is currently popular"

        reasons = []
        if reference_song["genre"] == candidate["genre"]:
            reasons.append(f"same genre ({candidate['genre']})")

        comparable_features = [
            ("energy", 0.12),
            ("danceability", 0.12),
            ("valence", 0.15),
            ("tempo", 12.0),
        ]

        for feature, threshold in comparable_features:
            source_value = float(reference_song[feature])
            candidate_value = float(candidate[feature])
            if abs(source_value - candidate_value) <= threshold:
                reasons.append(f"similar {feature}")

        if not reasons:
            reasons.append("similar audio profile")

        return "Recommended because it has " + ", ".join(reasons[:3])

    def _build_user_reason(self, interactions: list[dict[str, Any]], candidate: pd.Series) -> str:
        top_artists = [
            str(interaction["artist_name"])
            for interaction in interactions[:3]
            if interaction.get("artist_name")
        ]
        if not top_artists:
            return "Recommended from your Last.fm listening profile"

        return "Recommended from your Last.fm profile built from " + ", ".join(top_artists)

    def _build_collaborative_reason(self, interactions: list[dict[str, Any]], candidate: pd.Series) -> str:
        top_artists = [
            str(interaction["artist_name"])
            for interaction in interactions[:3]
            if interaction.get("artist_name")
        ]
        if not top_artists:
            return "Recommended because similar Last.fm users listened to this artist"

        return (
            "Recommended because similar Last.fm users who listened to "
            + ", ".join(top_artists)
            + " also listened to related artists"
        )

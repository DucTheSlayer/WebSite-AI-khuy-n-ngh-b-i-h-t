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
    """
    Hàm chuẩn hóa tên nghệ sĩ/ca sĩ để tránh việc so khớp bị lệch do lỗi gõ chữ hoặc ký tự đặc biệt.
    Ví dụ: 'Ca Sĩ A' và 'ca si a' sẽ được quy về cùng một dạng chuẩn là 'ca si a'.
    - Loại bỏ dấu tiếng Việt hoặc các ký tự Unicode kết hợp (diacritics).
    - Chuyển thành chữ thường.
    - Loại bỏ các ký tự đặc biệt, chỉ giữ lại chữ cái và chữ số.
    - Xóa khoảng trắng thừa.
    """
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


class ContentBasedRecommender:
    """
    Lớp chính chịu trách nhiệm triển khai hệ thống gợi ý âm nhạc Hybrid (Lai ghép).
    Hệ thống kết hợp giữa:
    1. Content-Based Filtering (Gợi ý dựa trên nội dung): Phân tích đặc trưng âm thanh Spotify (danceability, energy, tempo,...)
       và thể loại nhạc (genre) thông qua khoảng cách Cosine Similarity.
    2. Collaborative Filtering (Lọc cộng tác): Phân tích tương tác người dùng - nghệ sĩ từ dữ liệu Last.fm để tìm
       ra gu âm nhạc tương tự giữa các tài khoản khác nhau.
    3. Real-time Feedback Loop: Nhận tín hiệu Thích/Ghét từ người dùng trên Web để tức thời cập nhật kết quả gợi ý.
    """

    # Danh sách đầy đủ các cột dữ liệu trong file CSV dataset.csv
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

    # Các cột đặc trưng số học (Audio Features) dùng để tính toán độ tương tự âm nhạc
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
        use_feature_weights: bool = True,
    ) -> None:
        """
        Khởi tạo đối tượng gợi ý:
        - Đọc và làm sạch tập dữ liệu bài hát (dataset.csv)
        - Chuẩn hóa các thông số âm thanh và lập chỉ mục nhanh bài hát
        - Tải dữ liệu Last.fm (nếu có) để phục vụ cho thuật toán Collaborative Filtering
        """
        self.dataset_path = Path(dataset_path)
        self.user_interactions_path = Path(user_interactions_path) if user_interactions_path else None
        self.use_feature_weights = use_feature_weights
        self.user_interactions: dict[str, list[dict[str, Any]]] | None = None
        self.user_artist_weights: dict[str, dict[str, float]] | None = None
        self.artist_user_weights: dict[str, list[tuple[str, float]]] | None = None
        self.user_weight_norms: dict[str, float] | None = None
        # Khởi tạo bộ nhớ tạm để lưu phản hồi Thích (1) hoặc Ghét (-1) thời gian thực của người dùng
        self.user_feedback: dict[str, dict[str, int]] = {}
        # Từ điển lưu trị số nghịch đảo tần suất xuất hiện nghệ sĩ (IDF) nhằm giảm trọng số của nghệ sĩ quá đại trà
        self.artist_idf: dict[str, float] = {}

        # 1. Đọc tệp dữ liệu bài hát
        self.df = self._load_dataset()
        self.feature_columns = list(self.FEATURE_COLUMNS)
        self.track_count = len(self.df)
        
        # 2. Xây dựng ma trận đặc trưng số học (Feature Matrix) chuẩn hóa bằng StandardScaler và One-Hot thể loại
        self._build_feature_matrix()
        
        # 3. Lập chỉ mục nghệ sĩ để tìm kiếm nhanh nghệ sĩ liên quan
        self._build_artist_index()
        
        # Tạo danh sách bài hát phổ biến sẵn phục vụ cho trường hợp máy chủ gặp sự cố (Fallback)
        self.popular_df = self.df.sort_values(
            by=["popularity", "track_name"],
            ascending=[False, True],
        ).reset_index(drop=True)

    def _load_dataset(self) -> pd.DataFrame:
        """
        Đọc tệp dữ liệu bài hát dataset.csv và xử lý các lỗi dữ liệu:
        - Bỏ qua các dòng bị lỗi font hoặc sai số cột.
        - Chuyển các cột đặc trưng âm thanh về kiểu số (numeric), điền giá trị trung vị (median) nếu bị khuyết.
        - Chuẩn hóa cột explicit (có lời tục tĩu hay không) thành 0 hoặc 1.
        - Loại bỏ các bản ghi trùng lặp mã bài hát (track_id).
        """
        rows = []
        with self.dataset_path.open("r", encoding="utf-8") as dataset_file:
            reader = csv.reader(dataset_file)
            next(reader, None)  # Bỏ qua dòng tiêu đề.
            for raw_row in reader:
                normalized_row = self._normalize_row(raw_row)
                if normalized_row is None:
                    continue
                rows.append(normalized_row)

        df = pd.DataFrame(rows, columns=self.DATASET_COLUMNS)

        # Đổi tên cột cho tương thích với mô hình
        rename_map = {
            "artists": "artist",
            "album_name": "album",
            "track_genre": "genre",
        }
        df = df.rename(columns=rename_map)

        required_columns = {"track_id", "track_name", "artist", "album", "genre"}
        missing = required_columns - set(df.columns)
        if missing:
            raise ValueError(f"Tập dữ liệu thiếu các cột bắt buộc: {sorted(missing)}")

        # Ép kiểu dữ liệu số học cho các cột đặc trưng âm thanh
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

        # Điền các ô dữ liệu bị rỗng (NaN) bằng giá trị trung vị (median) của cột đó để tránh lỗi tính toán
        df[self.FEATURE_COLUMNS] = df[self.FEATURE_COLUMNS].fillna(df[self.FEATURE_COLUMNS].median())
        df["track_name"] = df["track_name"].fillna("").astype(str).str.strip()
        df["artist"] = df["artist"].fillna("").astype(str).str.strip()
        df["album"] = df["album"].fillna("").astype(str).str.strip()
        df["genre"] = df["genre"].fillna("unknown").astype(str).str.strip()

        # Loại bỏ các bài hát không có ID hoặc trùng lặp ID
        return df.dropna(subset=["track_id"]).drop_duplicates(subset=["track_id"]).reset_index(drop=True)

    def _normalize_row(self, raw_row: list[str]) -> list[str] | None:
        """
        Hàm chuẩn hóa sửa lỗi lệch cột do dữ liệu gốc CSV chứa dấu phẩy sai định dạng.
        """
        if len(raw_row) == len(self.DATASET_COLUMNS):
            return raw_row

        if len(raw_row) == len(self.DATASET_COLUMNS) + 1 and raw_row[15] == "":
            fixed_row = raw_row[:15] + [raw_row[16].replace("danceability", "")] + raw_row[17:]
            return fixed_row if len(fixed_row) == len(self.DATASET_COLUMNS) else None

        return None

    def _build_feature_matrix(self) -> None:
        """
        Xây dựng và chuẩn hóa ma trận đặc trưng số học cho thuật toán gợi ý:
        - Sử dụng StandardScaler: Vì các đặc trưng như Tempo (80-200 BPM), Loudness (-60 đến 0 dB),
          Duration (hàng trăm nghìn ms) có thang đo quá lớn so với Danceability hoặc Energy (chỉ từ 0 đến 1).
          StandardScaler đưa tất cả về cùng một phân phối chuẩn (trung bình = 0, độ lệch chuẩn = 1), 
          giúp khoảng cách Cosine được tính toán một cách công bằng giữa tất cả các chiều đặc trưng.
        - CẢI TIẾN: Áp dụng trọng số đặc trưng (Feature Weighting) để tăng tầm ảnh hưởng của các thuộc tính quan trọng:
          Nhịp điệu (tempo), năng lượng (energy), độ dễ nhảy (danceability) và tâm trạng (valence).
          Đồng thời giảm mạnh độ ảnh hưởng của thời lượng bài hát (duration_ms) và tông nhạc (key).
        - Áp dụng One-Hot Encoding cho Thể loại nhạc (Genre): Chuyển đổi tên thể loại nhạc (ví dụ: pop, rock)
          thành các cột nhị phân (0 hoặc 1), nhân trọng số 0.35 để tạo sự giao thoa hoàn hảo giữa giai điệu 
          và thể loại.
        - Chuẩn hóa L2 Norm: Đưa tất cả vector bài hát về độ dài bằng 1, giúp phép tính Cosine Similarity sau này
          đơn giản chỉ là phép nhân ma trận (tích vô hướng).
        """
        feature_frame = self.df[self.FEATURE_COLUMNS].copy()
        scaler = StandardScaler()
        audio_features_scaled = scaler.fit_transform(feature_frame)

        # Nhân trọng số cho từng cột đặc trưng âm học nếu được kích hoạt
        if self.use_feature_weights:
            feature_weights = np.array([
                0.5,   # popularity
                0.1,   # duration_ms (giảm mạnh ảnh hưởng của độ dài bài hát)
                1.5,   # danceability (tăng mạnh độ nhảy)
                1.5,   # energy (tăng mạnh năng lượng nhạc sôi động)
                0.3,   # key (giảm)
                1.2,   # loudness (tăng nhẹ)
                0.5,   # mode
                0.8,   # speechiness
                1.0,   # acousticness
                1.0,   # instrumentalness
                0.6,   # liveness
                1.5,   # valence (tâm trạng tích cực - tăng mạnh)
                1.2,   # tempo (tốc độ - tăng nhẹ)
                0.2    # time_signature
            ])
            # Nhân trọng số cho từng cột đặc trưng âm học
            audio_features_scaled = audio_features_scaled * feature_weights

        # Chuyển đổi thể loại nhạc sang biểu diễn dạng vector số (One-Hot)
        genre_dummies = pd.get_dummies(self.df["genre"], prefix="genre")
        genre_features = genre_dummies.astype(float).to_numpy()
        # Trọng số 0.35 được áp dụng để cân bằng giữa cấu trúc bài hát (65%) và nhãn thể loại (35%)
        genre_features_weighted = genre_features * 0.35

        # Ghép ma trận đặc trưng âm thanh và ma trận thể loại nhạc lại làm một
        self.feature_matrix = np.hstack([audio_features_scaled, genre_features_weighted])
        # Chuẩn hóa L2 Norm để việc nhân tích vô hướng chính là giá trị Cosine Similarity
        self.normalized_feature_matrix = self._normalize_matrix(self.feature_matrix)
        # Bản đồ ánh xạ từ track_id sang vị trí hàng trong ma trận
        self.track_index = {
            track_id: index for index, track_id in enumerate(self.df["track_id"].tolist())
        }

        # Tạo điểm phổ biến chuẩn hóa từ 0 đến 1 để bổ sung nhẹ vào điểm đánh giá gợi ý
        popularity = self.df["popularity"].fillna(0).astype(float).to_numpy()
        popularity_range = popularity.max() - popularity.min()
        self.popularity_score = (
            (popularity - popularity.min()) / popularity_range
            if popularity_range
            else np.zeros_like(popularity)
        )

    def _build_artist_index(self) -> None:
        """
        Xây dựng chỉ mục nhanh cho nghệ sĩ:
        - Ánh xạ từ nghệ sĩ sang danh sách bài hát của họ.
        - Tính vector đặc trưng trung bình của từng nghệ sĩ (Artist Profile) để làm cơ sở gợi ý.
        """
        self.track_artist_tokens: list[set[str]] = []
        self.artist_to_indices: dict[str, list[int]] = {}

        for index, artists in enumerate(self.df["artist"].tolist()):
            # Tách các nghệ sĩ bằng dấu chấm phẩy (nếu bài hát có nhiều ca sĩ song ca)
            artist_tokens = {
                normalized_artist
                for artist in str(artists).split(";")
                if (normalized_artist := normalize_artist(artist))
            }
            self.track_artist_tokens.append(artist_tokens)

            for artist_token in artist_tokens:
                self.artist_to_indices.setdefault(artist_token, []).append(index)

        # Tính profile âm học trung bình cho từng nghệ sĩ từ tất cả các bài hát họ đã thể hiện
        self.artist_feature_profiles = {
            artist: self.feature_matrix[indices].mean(axis=0)
            for artist, indices in self.artist_to_indices.items()
        }

    def _normalize_matrix(self, matrix: np.ndarray) -> np.ndarray:
        """Chuẩn hóa L2 cho ma trận (độ dài vector = 1)"""
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return matrix / norms

    def _normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """Chuẩn hóa L2 cho một vector đơn lẻ"""
        norm = np.linalg.norm(vector)
        return vector / norm if norm else vector

    def recommend_by_track(
        self,
        track_id: str,
        top_n: int = 10,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Thuật toán Content-Based chính: Gợi ý các bài hát tương tự theo một bài hát nguồn (Song Mode)
        - Tìm bài hát trong ma trận đặc trưng.
        - Nhân ma trận để tính nhanh Cosine Similarity của tất cả các bài hát khác với bài hát nguồn này.
        - Áp dụng các điều chỉnh trọng số (cộng điểm cùng thể loại, trừ điểm trùng lặp nghệ sĩ để tăng tính đa dạng).
        - Nếu người dùng đang đăng nhập (có user_id), lọc bỏ các bài hát mà tài khoản này đã nhấn DISLIKE.
        - Trả về top_n bài hát có điểm tương đồng cao nhất.
        """
        idx = self.track_index.get(track_id)
        if idx is None:
            return []

        # Lấy danh sách ID các bài hát bị người dùng Dislike trong phiên hiện tại để loại trừ
        disliked_tracks = set()
        if user_id and user_id in self.user_feedback:
            disliked_tracks = {tid for tid, val in self.user_feedback[user_id].items() if val == -1}

        source_song = self.df.iloc[idx]
        # Tính tích vô hướng -> cho ra giá trị Cosine Similarity ngay lập tức nhờ L2 Norm
        similarity_scores = self.normalized_feature_matrix @ self.normalized_feature_matrix[idx]
        # Điều chỉnh điểm số (thể loại nhạc, độ phổ biến, mức độ đa dạng nghệ sĩ)
        final_scores = self._apply_track_ranking_adjustments(
            source_index=idx,
            similarity_scores=similarity_scores,
        )

        recommendations = []
        # Quét qua các bài hát có điểm số cao nhất (sử dụng partition để lấy nhanh các ứng viên hàng đầu)
        for candidate_idx in self._rank_indices(final_scores, top_n=top_n, pool_multiplier=80):
            if candidate_idx == idx:
                continue

            candidate = self.df.iloc[candidate_idx]
            # Loại trừ tức thì bài hát bị Dislike
            if candidate["track_id"] in disliked_tracks:
                continue

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
        """
        Thuật toán gợi ý cá nhân hóa theo thông tin người dùng (User Mode):
        1. Lấy thông tin lịch sử tương tác ca sĩ của người dùng này (interactions).
        2. Tạo danh sách các nghệ sĩ người dùng đã biết/từng nghe (nếu exclude_known_artists=True) để loại trừ,
           giúp người dùng khám phá ra các ca sĩ mới lạ.
        3. Thực hiện gợi ý lai ghép (Hybrid) kết hợp Collaborative Filtering (Last.fm) và Content-Based (Spotify).
        """
        interactions = self.get_user_interactions(user_id)
        if not interactions:
            return []

        # Tạo tập hợp các nghệ sĩ đã nghe để lọc bỏ khỏi kết quả gợi ý mới
        excluded_artists = {
            interaction["normalized_artist"]
            for interaction in interactions
            if interaction.get("normalized_artist")
        } if exclude_known_artists else set()

        # Gọi hàm xử lý cốt lõi gợi ý dựa trên tương tác nghệ sĩ
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
        """
        Tính năng trộn gu âm nhạc 2 người (Taste Blend Mode):
        - Lấy lịch sử tương tác nghệ sĩ của 2 người dùng.
        - Xây dựng vector gu nhạc (User Profile) đại diện cho mỗi người dựa trên các bài hát và nghệ sĩ họ thích.
        - Tính góc Cosine Similarity giữa 2 vector cá nhân này làm Taste Match Score (Điểm tương đồng gu nhạc %).
        - Tạo vector chung (Blend Vector) bằng trung bình cộng 2 vector gu nhạc cá nhân (tỷ lệ 50:50).
        - Tính khoảng cách Cosine từ vector chung này tới tất cả bài hát trong kho dữ liệu, tìm ra các bài phù hợp.
        - Phân tích chi tiết mức độ đóng góp của từng người với bài hát gợi ý (Match Type):
          + "BOTH": Cả 2 người đều thích bài hát này rất nhiều.
          + "USER1": Thiên về gu nhạc của Người thứ nhất.
          + "USER2": Thiên về gu nhạc của Người thứ hai.
        - Lọc bỏ các bài hát bị DISLIKE bởi 1 trong 2 người.
        """
        # Lấy lịch sử nghe nhạc của 2 user
        interactions_1 = self.get_user_interactions(user_id_1)
        interactions_2 = self.get_user_interactions(user_id_2)

        # Xây dựng vector đặc trưng âm nhạc đại diện cho gu của mỗi người
        profile_1 = self._build_user_profile(interactions_1, user_id_1)
        profile_2 = self._build_user_profile(interactions_2, user_id_2)

        if profile_1 is None:
            profile_1 = np.zeros(self.feature_matrix.shape[1])
        if profile_2 is None:
            profile_2 = np.zeros(self.feature_matrix.shape[1])

        # Tính độ tương thích âm nhạc (Match Score) thông qua góc Cosine giữa 2 profile
        norm_1 = np.linalg.norm(profile_1)
        norm_2 = np.linalg.norm(profile_2)
        if norm_1 > 0 and norm_2 > 0:
            match_score = float(np.dot(profile_1, profile_2) / (norm_1 * norm_2))
            # Chuẩn hóa điểm số về khoảng [0, 1] để dễ hiển thị giao diện phần trăm
            match_score = max(0.0, min(1.0, (match_score + 1.0) / 2.0 if match_score < 0 else match_score))
        else:
            match_score = 0.5

        # Tạo vector gu nhạc giao thoa (Blend Vector) trung bình cộng của cả 2
        blend_vector = 0.5 * profile_1 + 0.5 * profile_2

        # Lấy danh sách ID các bài hát bị Dislike bởi 1 trong 2 người để loại trừ hoàn toàn
        disliked_tracks = set()
        for uid in [user_id_1, user_id_2]:
            if uid and uid in self.user_feedback:
                disliked_tracks.update({tid for tid, val in self.user_feedback[uid].items() if val == -1})

        excluded_artists = set()
        for inters in [interactions_1, interactions_2]:
            for interaction in inters:
                if interaction.get("normalized_artist"):
                    excluded_artists.add(interaction["normalized_artist"])

        # Chuẩn hóa vector blend
        normalized_blend = self._normalize_vector(blend_vector)
        # Tính điểm tương đồng Cosine giữa kho bài hát và gu nhạc chung của 2 người
        similarity_scores = self.normalized_feature_matrix @ normalized_blend
        # Cộng thêm một chút điểm ưu tiên cho bài hát phổ biến
        final_scores = similarity_scores + (self.popularity_score * 0.03)

        recommendations = []
        seen_track_ids = set()
        seen_artist_tokens = set()

        # Quét các ứng viên bài hát phù hợp nhất
        for candidate_idx in self._rank_indices(final_scores, top_n=top_n, pool_multiplier=220):
            candidate = self.df.iloc[candidate_idx]
            if candidate["track_id"] in seen_track_ids or candidate["track_id"] in disliked_tracks:
                continue

            # Đảm bảo tính đa dạng nghệ sĩ trong playlist Blend (tránh một ca sĩ chiếm quá nhiều bài)
            candidate_artists = self.track_artist_tokens[candidate_idx]
            if candidate_artists & seen_artist_tokens:
                continue

            candidate_feat = self.normalized_feature_matrix[candidate_idx]
            # Tính riêng xem bài hát này khớp bao nhiêu phần trăm với gu của User 1 và User 2
            sim_1 = float(np.dot(candidate_feat, self._normalize_vector(profile_1))) if norm_1 > 0 else 0.0
            sim_2 = float(np.dot(candidate_feat, self._normalize_vector(profile_2))) if norm_2 > 0 else 0.0

            # Phân loại lý do gợi ý trên giao diện
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
        """
        Hàm trung tâm thực hiện gợi ý cá nhân hóa lai ghép (Hybrid Recommendation):
        - BƯỚC 1: Gọi thuật toán Lọc cộng tác nghệ sĩ (User-Based Collaborative Filtering) qua Last.fm.
        - BƯỚC 2: Nếu chưa đủ top_n gợi ý, gọi thuật toán Lọc theo đặc trưng âm học (Content-Based) để bổ sung thêm bài hát.
        - Kết quả cuối cùng đảm bảo luôn đủ top_n bài hát và tự động loại bỏ các bài hát bị DISLIKE.
        """
        excluded_artists = excluded_artists or set()
        
        # 1. Chạy giải thuật Lọc cộng tác nghệ sĩ (Last.fm CF)
        collaborative_recommendations = self._recommend_with_artist_collaborative_filtering(
            interactions=interactions,
            top_n=top_n,
            excluded_artists=excluded_artists,
            source_user_id=source_user_id,
        )

        # 2. Nếu đã tìm đủ số lượng bài hát, trả về ngay lập tức
        if len(collaborative_recommendations) >= top_n:
            return collaborative_recommendations

        # 3. Nếu thiếu, chạy tiếp giải thuật gợi ý theo Đặc trưng âm học bài hát (Content-Based) để bổ sung
        return self._recommend_with_audio_content_filtering(
            interactions=interactions,
            top_n=top_n,
            collaborative_recommendations=collaborative_recommendations,
            excluded_artists=excluded_artists,
            source_user_id=source_user_id,
        )

    def _recommend_with_audio_content_filtering(
        self,
        interactions: list[dict[str, Any]],
        top_n: int,
        collaborative_recommendations: list[dict[str, Any]],
        excluded_artists: set[str],
        source_user_id: str | None,
    ) -> list[dict[str, Any]]:
        """
        BƯỚC PHỤ TRỢ (Fallback / Bổ sung): Gợi ý theo đặc trưng âm học bài hát (Content-Based)
        Tính toán gu nhạc trung bình của người dùng, quét kho nhạc và lấy ra các bài phù hợp nhất
        để bổ sung vào danh sách gợi ý cho đến khi đạt đủ số lượng top_n bài hát.
        """
        user_profile = self._build_user_profile(interactions, source_user_id)
        if user_profile is None:
            return collaborative_recommendations

        normalized_profile = self._normalize_vector(user_profile)
        similarity_scores = self.normalized_feature_matrix @ normalized_profile
        final_scores = similarity_scores + (self.popularity_score * 0.03)

        recommendations = list(collaborative_recommendations)
        seen_track_ids = {rec["track_id"] for rec in recommendations}
        seen_artist_tokens = set()
        for rec in recommendations:
            track_index = self.track_index.get(rec["track_id"])
            if track_index is not None:
                seen_artist_tokens.update(self.track_artist_tokens[track_index])

        # Lấy danh sách bài hát bị Dislike của user
        disliked_tracks = set()
        if source_user_id and source_user_id in self.user_feedback:
            disliked_tracks = {tid for tid, val in self.user_feedback[source_user_id].items() if val == -1}

        # Tìm kiếm ứng viên dựa trên độ tương đồng Cosine của đặc trưng âm học
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
        """Lấy lịch sử tương tác nghệ sĩ của 1 user cụ thể từ Last.fm dataset"""
        self._ensure_user_interactions_loaded()
        if self.user_interactions is None:
            return []
        return list(self.user_interactions.get(user_id, []))

    def get_demo_users(self, limit: int = 12) -> list[dict[str, Any]]:
        """Lấy danh sách các người dùng demo để hiển thị trên giao diện bạn bè (Friend Activity)"""
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
        """Lấy danh sách các bài hát phổ biến nhất trong hệ thống"""
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
        """
        Đọc và tải dữ liệu tương tác Last.fm từ file CSV (chỉ tải 1 lần đầu).
        Tính toán chỉ số IDF (Nghịch đảo tần suất tài liệu) của từng nghệ sĩ:
        Nghệ sĩ nào càng nhiều người nghe thì độ đặc trưng càng thấp (giống như từ dừng 'the', 'a' trong NLP),
        giúp làm nổi bật những nghệ sĩ ngách mang tính cá nhân cao.
        """
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

        # Tính toán IDF (Inverse Document Frequency) cho từng nghệ sĩ
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
        """
        Xây dựng chỉ mục ngược (Inverted Index) từ Nghệ sĩ -> Danh sách người dùng thích nghe họ.
        Điều này phục vụ đắc lực cho việc tìm nhanh các 'hàng xóm' (những người có gu giống nhau)
        trong thuật toán Lọc cộng tác (Collaborative Filtering).
        """
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
                    # Sử dụng log1p(plays) để giảm bớt sự thống trị của những ca khúc quá viral,
                    # đưa tần suất nghe (plays) về thang đo phi tuyến hợp lý
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
            # Lưu Norm L2 của vector người dùng để tính Cosine Similarity nhanh hơn
            norm = float(np.linalg.norm(list(artist_weights.values())))
            self.user_weight_norms[user_id] = norm if norm else 1.0

            for artist, weight in artist_weights.items():
                self.artist_user_weights.setdefault(artist, []).append((user_id, weight))

        # Sắp xếp các danh sách chỉ mục ngược theo thứ tự giảm dần của trọng số để dễ cắt tỉa (pruning)
        for postings in self.artist_user_weights.values():
            postings.sort(key=lambda user_weight: user_weight[1], reverse=True)

    def _recommend_with_artist_collaborative_filtering(
        self,
        interactions: list[dict[str, Any]],
        top_n: int,
        excluded_artists: set[str],
        source_user_id: str | None,
    ) -> list[dict[str, Any]]:
        """
        Giải thuật Lọc cộng tác nghệ sĩ (User-Based Collaborative Filtering):
        1. Tìm ra các người dùng hàng xóm có gu nghe nhạc tương đồng với người dùng hiện tại (qua Cosine Similarity).
        2. Tổng hợp các nghệ sĩ mà những hàng xóm này hay nghe nhưng người dùng hiện tại chưa nghe.
        3. Chọn ra bài hát tốt nhất của những nghệ sĩ này dựa trên sự kết hợp giữa:
           - Điểm gợi ý nghệ sĩ từ cộng đồng hàng xóm (weight 1.0)
           - Điểm tương đồng giai điệu (Content Score) với gu cá nhân (weight 0.18)
           - Điểm phổ biến (Popularity Score) của bài hát (weight 0.08)
        """
        artist_scores = self._score_candidate_artists_from_neighbors(
            interactions=interactions,
            excluded_artists=excluded_artists,
            source_user_id=source_user_id,
        )
        if not artist_scores:
            return []

        # Xây dựng profile gu nhạc cá nhân để tính điểm giai điệu (Content Score)
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

        # Loại trừ các bài hát bị DISLIKE
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

                # Công thức phối hợp lai ghép tính điểm xếp hạng bài hát gợi ý
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
        """
        Tìm kiếm các người dùng 'láng giềng' có sở thích nghệ sĩ tương tự 
        và tính điểm cho các nghệ sĩ tiềm năng mà láng giềng thích nhưng ta chưa từng nghe.
        """
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

        # Duyệt qua các nghệ sĩ người dùng thích để tìm các tài khoản hàng xóm từng nghe nghệ sĩ này
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

        # Tính toán điểm tương đồng Cosine chuẩn hóa giữa ta và các hàng xóm
        ranked_neighbors = []
        for neighbor_user_id, raw_score in neighbor_scores.items():
            neighbor_norm = self.user_weight_norms.get(neighbor_user_id, 1.0)
            ranked_neighbors.append((
                neighbor_user_id,
                raw_score / (target_norm * neighbor_norm),
            ))

        ranked_neighbors.sort(key=lambda item: item[1], reverse=True)

        # Lấy danh sách các nghệ sĩ được nghe bởi các láng giềng gần nhất làm nghệ sĩ ứng viên
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
        """
        Xây dựng vector gu nhạc đại diện cho người dùng (User Profile):
        - Cộng gộp các vector đặc trưng của các nghệ sĩ người dùng hay nghe, nhân với trọng số nghe (plays).
        - Nếu người dùng có các bài hát bấm LIKE trên Web, lấy vector đặc trưng của các bài hát đã LIKE
          để pha trộn thêm vào vector gu nhạc (với tỷ lệ: 60% gu lịch sử + 40% tương tác LIKE mới nhất).
          Cơ chế này giúp thuật toán gợi ý cập nhật tức thời gu nhạc theo tương tác của người dùng.
        """
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

        # Tích hợp phản hồi LIKE thực tế trên web vào Profile gu nhạc
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
                        # Kết hợp gu nhạc cũ và gu nhạc mới cập nhật (LIKEs)
                        base_profile = base_profile * 0.6 + liked_mean * 0.4
                    else:
                        base_profile = liked_mean

        return base_profile

    def add_user_feedback(self, user_id: str, track_id: str, feedback_type: str) -> None:
        """
        Ghi nhận lượt Like (1) hoặc Dislike (-1) vào bộ nhớ tạm in-memory của AI service.
        CẢI TIẾN: Nếu người dùng bấm LIKE bài hát, hệ thống sẽ tự động lấy thông tin nghệ sĩ chính
        của bài hát đó và thêm vào lịch sử nghe nhạc Last.fm của họ với số lượt nghe plays = 100.
        Việc này giúp thuật toán Lọc cộng tác (Collaborative Filtering) phản hồi thời gian thực tức thời theo gu nhạc.
        """
        if user_id not in self.user_feedback:
            self.user_feedback[user_id] = {}
        val = 1 if feedback_type.upper() == "LIKE" else -1
        self.user_feedback[user_id][track_id] = val

        # Đồng bộ lượt LIKE sang Lọc cộng tác
        if feedback_type.upper() == "LIKE":
            idx = self.track_index.get(track_id)
            if idx is not None:
                song_info = self.df.iloc[idx]
                song_artist = str(song_info["artist"]).split(";")[0] # Lấy nghệ sĩ chính
                
                self._ensure_user_interactions_loaded()
                if self.user_interactions is not None:
                    user_ints = self.user_interactions.setdefault(user_id, [])
                    # Tránh thêm trùng nghệ sĩ đã có trong lịch sử của user này
                    exists = any(item.get("normalized_artist") == normalize_artist(song_artist) for item in user_ints)
                    if not exists:
                        user_ints.append({
                            "artist_name": song_artist,
                            "normalized_artist": normalize_artist(song_artist),
                            "plays": 100,
                            "weight": 10.0
                        })
                        # Lập lại chỉ mục để cập nhật thuật toán
                        self._build_user_interaction_indexes()

    def reset_user_feedback(self, user_id: str) -> None:
        """Xóa sạch tương tác cũ của tài khoản để học lại gu nhạc từ đầu"""
        if user_id in self.user_feedback:
            self.user_feedback[user_id] = {}

    def _apply_track_ranking_adjustments(
        self,
        source_index: int,
        similarity_scores: np.ndarray,
    ) -> np.ndarray:
        """
        Hàm tinh chỉnh xếp hạng gợi ý bài hát:
        - Cộng thêm 0.05 điểm cho những bài cùng Thể loại nhạc (Genre) với bài hát nguồn.
        - Cộng thêm tối đa 0.02 điểm thưởng dựa trên độ phổ biến của bài hát (Popularity).
        - Trừ bớt 0.015 điểm nếu bài hát của cùng nghệ sĩ thể hiện (tránh đề xuất 1 danh sách toàn bài của cùng 1 nghệ sĩ).
        - Đặt điểm bài hát gốc bằng âm vô cùng để loại trừ nó tự gợi ý lại chính nó.
        """
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
        """
        Hàm sắp xếp vị trí các bài hát có điểm số cao nhất.
        Sử dụng np.argpartition để chỉ sắp xếp một phần tử lớn nhất (chạy cực nhanh thay vì sort toàn bộ 110.000 bài).
        """
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
        """Tạo gói dữ liệu phản hồi JSON chuẩn hóa về thông tin bài hát gửi lên Spring Boot"""
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
        """Sinh ra giải thích lý do gợi ý dựa trên sự tương đồng các thuộc tính âm thanh"""
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
        """Sinh ra giải thích lý do gợi ý dựa trên nghệ sĩ hàng đầu từ hồ sơ cá nhân"""
        top_artists = [
            str(interaction["artist_name"])
            for interaction in interactions[:3]
            if interaction.get("artist_name")
        ]
        if not top_artists:
            return "Recommended from your Last.fm listening profile"

        return "Recommended from your Last.fm profile built from " + ", ".join(top_artists)

    def _build_collaborative_reason(self, interactions: list[dict[str, Any]], candidate: pd.Series) -> str:
        """Sinh ra giải thích lý do gợi ý lọc cộng tác (dựa trên sở thích của những người dùng tương đồng)"""
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

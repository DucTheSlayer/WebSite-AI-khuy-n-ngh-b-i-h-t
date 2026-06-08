# Cập Nhật Hướng Hybrid Recommendation

## 1. Bộ Dữ Liệu Đang Khai Thác

Hệ thống hiện sử dụng 2 nguồn dữ liệu chính:

1. `data/dataset.csv`
   - Dữ liệu bài hát, nghệ sĩ, thể loại, độ phổ biến và audio features.
   - Dùng cho content-based recommendation theo bài hát.

2. `data/usersha1-artmbid-artname-plays.tsv`
   - Dữ liệu Last.fm user nghe artist theo số lượt nghe `plays`.
   - Không xem `plays` là rating trực tiếp, mà xem là implicit feedback.
   - Đã xử lý thành `data/lastfm_user_artist_interactions.csv`.

Kết quả xử lý Last.fm:

```text
Eligible users: 50,000
Clean interactions: 1,260,419
Matched artists: 8,731
Matched row rate: ~50.01%
Weight formula: weight = log1p(plays)
```

## 2. Thuật Toán Hiện Tại

### Content-Based Recommendation

Input là một `track_id`. Hệ thống lấy vector audio features của bài hát, chuẩn hóa bằng `StandardScaler`, sau đó tính cosine similarity với toàn bộ bài hát còn lại.

Điểm xếp hạng được điều chỉnh thêm:

```text
final_score = cosine_similarity
            + same_genre_bonus
            + popularity_bonus
            - same_artist_penalty
```

### Hybrid User Profile Recommendation

Input là một `user_id` Last.fm. Hệ thống lấy các artist user đã nghe, dùng `plays` để tạo trọng số:

```text
weight = log1p(plays)
```

Phiên bản trước chỉ map artist sang các bài hát trong `dataset.csv`, lấy trung bình audio features theo trọng số để tạo user profile:

```text
user_profile = weighted_average(artist_audio_feature_vectors)
```

Sau khi đánh giá, mô hình đã được cải thiện bằng cách bổ sung tầng collaborative filtering trên dữ liệu Last.fm:

```text
1. Từ các artist user đã nghe, tìm các Last.fm users có gu nghe gần giống.
2. Tính độ tương đồng user-user dựa trên artist overlap và trọng số log1p(plays).
3. Lấy các artist mà nhóm user tương tự nghe nhưng user hiện tại chưa nghe.
4. Map candidate artists sang các track trong Spotify dataset.
5. Xếp hạng track bằng:
   - collaborative artist score
   - content/audio similarity với user profile
   - popularity bonus nhẹ
```

Công thức xếp hạng hiện tại ở mức khái quát:

```text
score(user, song) =
    collaborative_artist_score
  + audio_profile_similarity
  + popularity_bonus
```

## 3. API Đã Bổ Sung

FastAPI:

```text
GET /recommend/{track_id}
GET /recommend/user/{user_id}
GET /users/demo
GET /popular
GET /health
```

Spring Boot:

```text
GET /api/recommend/{trackId}
GET /api/recommend/user/{userId}
GET /api/users/demo
GET /api/popular
GET /api/songs
```

## 4. Giao Diện Đã Bổ Sung

Frontend React hiện hỗ trợ 2 chế độ:

```text
Song mode: chọn bài hát để xem bài tương tự.
User mode: chọn Last.fm demo user để xem gợi ý cá nhân hóa.
```

## 5. Đánh Giá Mô Hình

Script đánh giá:

```text
evaluate_hybrid.py
```

Cách đánh giá:

```text
Với mỗi user:
- chia artist đã nghe thành train/test
- dùng train để tạo user profile
- recommend top K bài hát
- nếu artist của bài recommend nằm trong test set thì tính là hit
```

Metrics:

```text
Precision@K
Recall@K
HitRate@K
NDCG@K
Coverage / unique recommended tracks
```

Kết quả sau khi bổ sung collaborative artist scoring, đánh giá trên 1,000 users:

| K | Precision@K | Recall@K | HitRate@K | NDCG@K |
|---|---:|---:|---:|---:|
| 5 | 0.1402 | 0.136523 | 0.506 | 0.170251 |
| 10 | 0.1080 | 0.210327 | 0.625 | 0.196841 |
| 20 | 0.0794 | 0.309010 | 0.756 | 0.241140 |

So với phiên bản user-profile chỉ dựa trên audio features, HitRate@20 tăng từ 0.141 lên 0.756. Điều này cho thấy tầng collaborative filtering khai thác dữ liệu Last.fm hiệu quả hơn cho bài toán dự đoán artist sở thích bị ẩn.

## 6. Định Hướng Tiếp Tục

Các bước tiếp theo:

```text
1. Thêm popularity baseline để so sánh với hybrid collaborative.
2. Tối ưu tham số collaborative filtering: số seed artists, số neighbor users, popularity weight.
3. Thêm caching cho FastAPI để giảm thời gian load user interactions.
4. Thêm lưu feedback thật từ web: like/dislike/click.
5. Tối ưu ranking để cân bằng similarity, popularity, diversity và artist novelty.
```

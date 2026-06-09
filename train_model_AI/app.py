import os
import re
import sys
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

# Thêm thư mục hiện tại vào sys.path để Python có thể import file recommender.py
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

# Import class chính chịu trách nhiệm gợi ý từ file recommender.py
from recommender import ContentBasedRecommender


def get_data_path(filename: str) -> Path:
    """
    Hàm hỗ trợ tìm đường dẫn chính xác của file dữ liệu (.csv) trong thư mục 'data'.
    Nó sẽ tìm trong thư mục hiện tại trước, nếu không thấy sẽ tìm ở thư mục cha.
    """
    path_inside = BASE_DIR / "data" / filename
    if path_inside.exists():
        return path_inside.resolve()
    return (BASE_DIR.parent / "data" / filename).resolve()


# Xác định đường dẫn file dataset bài hát (dataset.csv) và tương tác Last.fm
DATASET_ENV = os.getenv("MUSIC_DATASET_PATH")
DATASET_PATH = Path(DATASET_ENV) if DATASET_ENV else get_data_path("dataset.csv")

LASTFM_ENV = os.getenv("LASTFM_INTERACTIONS_PATH")
LASTFM_PATH = Path(LASTFM_ENV) if LASTFM_ENV else get_data_path("lastfm_user_artist_interactions.csv")

# Khởi tạo ứng dụng FastAPI làm AI Service
app = FastAPI(title="Music Recommender AI Service", version="1.0.0")


@lru_cache(maxsize=1)
def get_recommender() -> ContentBasedRecommender:
    """
    Sử dụng lru_cache để chỉ khởi tạo đối tượng recommender DUY NHẤT một lần (Singleton).
    Tránh việc load lại file dữ liệu CSV dung lượng lớn ở mỗi request, giúp tối ưu RAM.
    """
    return ContentBasedRecommender(DATASET_PATH, LASTFM_PATH)


@app.get("/")
def home():
    """Endpoint kiểm tra dịch vụ AI hoạt động"""
    return {"message": "AI service running"}


@app.get("/health")
def health():
    """Endpoint kiểm tra trạng thái sức khỏe của AI model (số lượng bài hát, các đặc trưng đã load)"""
    recommender = get_recommender()
    return {
        "status": "ok",
        "tracks": recommender.track_count,
        "features": recommender.feature_columns,
        "lastfm_interactions_available": LASTFM_PATH.exists(),
    }


@app.get("/recommend/blend")
def recommend_blend(
    user1: str,
    user2: str,
    top_n: int = Query(default=10, ge=1, le=50)
):
    """
    API Gợi ý chung cho 2 người (Taste Blend):
    Tính toán gu nhạc giao thoa giữa user1 và user2 và trả về playlist chung kèm điểm tương đồng.
    """
    recommender = get_recommender()
    try:
        return recommender.recommend_blend(user_id_1=user1, user_id_2=user2, top_n=top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recommend/user/{user_id}")
def recommend_for_user(user_id: str, top_n: int = Query(default=10, ge=1, le=50)):
    """
    API Gợi ý cá nhân hóa dựa trên tên người dùng (User Mode):
    Dùng Collaborative Filtering từ dữ liệu Last.fm kết hợp với Audio Features của Spotify.
    """
    recommender = get_recommender()
    recommendations = recommender.recommend_by_user(user_id=user_id, top_n=top_n)

    if not recommendations:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found or has no matched artists")

    return {
        "user_id": user_id,
        "recommendations": recommendations,
    }


@app.get("/recommend/{track_id}")
def recommend(
    track_id: str,
    top_n: int = Query(default=10, ge=1, le=50),
    user_id: str | None = None
):
    """
    API Gợi ý bài hát tương đồng (Song Mode):
    Tìm các bài hát tương tự bài hát đầu vào dựa trên Cosine Similarity của Audio Features.
    Nếu người dùng đang đăng nhập (có user_id), hệ thống sẽ tự lọc bỏ các bài hát bị Dislike.
    """
    recommender = get_recommender()
    recommendations = recommender.recommend_by_track(track_id=track_id, top_n=top_n, user_id=user_id)

    if not recommendations:
        raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

    return {
        "track_id": track_id,
        "recommendations": recommendations,
    }


@app.get("/users/demo")
def demo_users(limit: int = Query(default=12, ge=1, le=50)):
    """API lấy danh sách tài khoản demo từ Last.fm để test tính năng gợi ý theo User hoặc Blend"""
    recommender = get_recommender()
    return {
        "users": recommender.get_demo_users(limit=limit),
    }


@app.get("/popular")
def popular(top_n: int = Query(default=10, ge=1, le=50)):
    """API lấy danh sách bài hát phổ biến nhất trong hệ thống"""
    recommender = get_recommender()
    return {
        "recommendations": recommender.get_popular(top_n=top_n),
    }


# Định nghĩa cấu trúc dữ liệu feedback gửi lên từ Spring Boot
class FeedbackModel(BaseModel):
    user_id: str
    track_id: str
    feedback_type: str  # "LIKE" hoặc "DISLIKE"


@app.post("/feedback")
def submit_feedback(data: FeedbackModel):
    """
    API ghi nhận phản hồi (Like/Dislike) từ người dùng thực trên web:
    Cập nhật dữ liệu in-memory để AI model cập nhật gu nhạc ngay lập tức.
    """
    recommender = get_recommender()
    try:
        recommender.add_user_feedback(
            user_id=data.user_id,
            track_id=data.track_id,
            feedback_type=data.feedback_type
        )
        return {"status": "success", "message": f"Feedback {data.feedback_type} recorded for user {data.user_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/feedback/reset/{user_id}")
def reset_feedback(user_id: str):
    """API xóa sạch lịch sử Like/Dislike của người dùng để reset gu nhạc"""
    recommender = get_recommender()
    try:
        recommender.reset_user_feedback(user_id=user_id)
        return {"status": "success", "message": f"Feedback reset for user {user_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/youtube/search")
def youtube_search(q: str = Query(...)):
    """
    Hàm cào dữ liệu (Scraping) YouTube:
    Tự động tìm kiếm từ khóa trên YouTube và trích xuất Video ID của bài hát để trình phát iframe
    ở frontend có thể phát MV bài hát đó trực tiếp.
    """
    try:
        search_keyword = urllib.parse.quote(q)
        url = f"https://www.youtube.com/results?search_query={search_keyword}"
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8')
            
        video_ids = re.findall(r"watch\?v=(\S{11})", html)
        if not video_ids:
            video_ids = re.findall(r'"videoId":"(\S{11})"', html)
            
        if video_ids:
            return {"video_id": video_ids[0]}
            
        return {"video_id": ""}
    except Exception as e:
        return {"video_id": "", "error": str(e)}

import os
import re
import sys
import urllib.parse
import urllib.request
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from recommender import ContentBasedRecommender


def get_data_path(filename: str) -> Path:
    # Check if data directory is inside train_model_AI (CWD)
    path_inside = BASE_DIR / "data" / filename
    if path_inside.exists():
        return path_inside.resolve()
    # Otherwise fallback to parent directory
    return (BASE_DIR.parent / "data" / filename).resolve()


DATASET_ENV = os.getenv("MUSIC_DATASET_PATH")
DATASET_PATH = Path(DATASET_ENV) if DATASET_ENV else get_data_path("dataset.csv")

LASTFM_ENV = os.getenv("LASTFM_INTERACTIONS_PATH")
LASTFM_PATH = Path(LASTFM_ENV) if LASTFM_ENV else get_data_path("lastfm_user_artist_interactions.csv")

app = FastAPI(title="Music Recommender AI Service", version="1.0.0")


@lru_cache(maxsize=1)
def get_recommender() -> ContentBasedRecommender:
    return ContentBasedRecommender(DATASET_PATH, LASTFM_PATH)


@app.get("/")
def home():
    return {"message": "AI service running"}


@app.get("/health")
def health():
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
    recommender = get_recommender()
    try:
        return recommender.recommend_blend(user_id_1=user1, user_id_2=user2, top_n=top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/recommend/user/{user_id}")
def recommend_for_user(user_id: str, top_n: int = Query(default=10, ge=1, le=50)):
    recommender = get_recommender()
    recommendations = recommender.recommend_by_user(user_id=user_id, top_n=top_n)

    if not recommendations:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found or has no matched artists")

    return {
        "user_id": user_id,
        "recommendations": recommendations,
    }


@app.get("/recommend/{track_id}")
def recommend(track_id: str, top_n: int = Query(default=10, ge=1, le=50)):
    recommender = get_recommender()
    recommendations = recommender.recommend_by_track(track_id=track_id, top_n=top_n)

    if not recommendations:
        raise HTTPException(status_code=404, detail=f"Track {track_id} not found")

    return {
        "track_id": track_id,
        "recommendations": recommendations,
    }




@app.get("/users/demo")
def demo_users(limit: int = Query(default=12, ge=1, le=50)):
    recommender = get_recommender()
    return {
        "users": recommender.get_demo_users(limit=limit),
    }


@app.get("/popular")
def popular(top_n: int = Query(default=10, ge=1, le=50)):
    recommender = get_recommender()
    return {
        "recommendations": recommender.get_popular(top_n=top_n),
    }


class FeedbackModel(BaseModel):
    user_id: str
    track_id: str
    feedback_type: str  # "LIKE" hoặc "DISLIKE"


@app.post("/feedback")
def submit_feedback(data: FeedbackModel):
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
    recommender = get_recommender()
    try:
        recommender.reset_user_feedback(user_id=user_id)
        return {"status": "success", "message": f"Feedback reset for user {user_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/youtube/search")
def youtube_search(q: str = Query(...)):
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

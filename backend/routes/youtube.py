from fastapi import APIRouter, Query, HTTPException, Depends
import requests
import json
import os
from datetime import datetime

from backend.config import YOUTUBE_KEYS, current_key_index
from backend.utils.key_manager import make_youtube_request
from backend.routes.auth import get_current_user

router = APIRouter(prefix="/api/youtube", tags=["YouTube"])

LIKED_PATH = "backend/data/liked_songs.json"
RECENT_PATH = "backend/data/recently_played.json"
ANALYTICS_PATH = "backend/data/analytics.json"

# Ensure data files exist
os.makedirs("backend/data", exist_ok=True)
for path in [LIKED_PATH, RECENT_PATH]:
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)

if not os.path.exists(ANALYTICS_PATH):
    with open(ANALYTICS_PATH, "w") as f:
        json.dump({}, f, indent=2)


GENRE_KEYWORDS = {
    "hip hop": ["drake", "eminem", "rap", "trap", "hiphop", "kendrick", "21 savage", "lil", "asap"],
    "pop": ["taylor swift", "selena", "ariana", "justin bieber", "weeknd", "dua lipa", "pop"],
    "rock": ["nirvana", "metallica", "rock", "guitar", "foo fighters", "linkin park"],
    "electronic": ["edm", "avicii", "marshmello", "electronic", "club", "zedd", "alan walker"],
    "lofi": ["lofi", "study", "chill", "beats", "ambient", "focus"],
    "classical": ["mozart", "beethoven", "symphony", "orchestra", "vivaldi", "piano"]
}


@router.get("/search")
def search_youtube(query: str = Query(..., min_length=1)):
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "videoCategoryId": "10",
        "maxResults": 5
    }
    try:
        data = make_youtube_request("https://www.googleapis.com/youtube/v3/search", params)
        items = data.get("items", [])
        return {"results": [
            {
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "videoId": item["id"]["videoId"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"]
            } for item in items if "videoId" in item["id"]
        ]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube API error: {str(e)}")

@router.get("/play/{video_id}")
def play_youtube(video_id: str, username: str = Depends(get_current_user)):
    print(f"🎧 {username} played {video_id}")
    try:
        genre = classify_genre(video_id)["genre"]

        # ✅ Save to recently played
        with open(RECENT_PATH, "r+") as f:


            data = json.load(f)
            history = data.get(username, [])
            history = [h for h in history if h["videoId"] != video_id]
            history.insert(0, {
                "videoId": video_id,
                "genre": genre,
                "timestamp": datetime.utcnow().isoformat()
            })
            data[username] = history[:10]
            f.seek(0)
            json.dump(data, f, indent=2)
            f.truncate()

        # ✅ Log Analytics
        with open(ANALYTICS_PATH, "r+") as f:
            analytics = json.load(f)
            user_data = analytics.get(username, {
                "play_count": 0,
                "song_counts": {},
                "last_play": ""
            })

            user_data["play_count"] += 1
            user_data["last_play"] = datetime.utcnow().isoformat()
            user_data["song_counts"][video_id] = user_data["song_counts"].get(video_id, 0) + 1

            analytics[username] = user_data
            f.seek(0)
            json.dump(analytics, f, indent=2)
            f.truncate()

    except Exception as e:
        print(f"[Recently Played Error] {e}")

    return {
        "stream_url": f"https://www.youtube.com/watch?v={video_id}"
    }



@router.post("/like/{video_id}")
def like_song(video_id: str, username: str = Depends(get_current_user)):
    genre = classify_genre(video_id)["genre"]
    with open(LIKED_PATH, "r+") as f:
        data = json.load(f)
        liked = data.get(username, [])

        if any(item["videoId"] == video_id for item in liked):
            return {"message": "Already liked"}

        liked.insert(0, {"videoId": video_id, "genre": genre})
        data[username] = liked

        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()
    return {"message": "Song liked", "genre": genre}

@router.delete("/unlike/{video_id}")
def unlike_video(video_id: str, username: str = Depends(get_current_user)):
    with open(LIKED_PATH, "r+") as f:
        data = json.load(f)
        liked = data.get(username, [])
        liked = [item for item in liked if item["videoId"] != video_id]
        data[username] = liked

        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()
    return {"message": f"Video {video_id} unliked!"}

@router.get("/liked-details")
def get_liked_song_details(username: str = Depends(get_current_user)):
    with open(LIKED_PATH, "r") as f:
        data = json.load(f)
    liked_items = data.get(username, [])
    results = []
    for item in liked_items:
        video_id = item["videoId"]
        genre = item.get("genre", "unknown")
        params = {
            "part": "snippet",
            "id": video_id,
            "maxResults": 1
        }
        data = make_youtube_request("https://www.googleapis.com/youtube/v3/videos", params)
        if data["items"]:
            snippet = data["items"][0]["snippet"]
            results.append({
                "title": snippet["title"],
                "channel": snippet["channelTitle"],
                "videoId": video_id,
                "thumbnail": snippet["thumbnails"]["high"]["url"],
                "genre": genre
            })
    return {"liked_songs": results}

@router.get("/recommend")
def recommend_songs(username: str = Depends(get_current_user)):
    with open(LIKED_PATH, "r") as f:
        data = json.load(f)
    liked_items = data.get(username, [])
    if not liked_items:
        return {"recommendations": []}

    query_terms = []
    for item in liked_items[-3:]:
        video_id = item["videoId"]
        params = {
            "part": "snippet",
            "id": video_id,
            "maxResults": 1
        }
        data = make_youtube_request("https://www.googleapis.com/youtube/v3/videos", params)
        if data["items"]:
            title = data["items"][0]["snippet"]["title"]
            keyword = title.split(" ")[0]
            query_terms.append(keyword)

    results = []
    for keyword in query_terms:
        params = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "videoCategoryId": "10",
            "maxResults": 5
        }
        search_data = make_youtube_request("https://www.googleapis.com/youtube/v3/search", params)
        for item in search_data["items"]:
            if "videoId" in item["id"]:
                results.append({
                    "title": item["snippet"]["title"],
                    "channel": item["snippet"]["channelTitle"],
                    "videoId": item["id"]["videoId"],
                    "thumbnail": item["snippet"]["thumbnails"]["high"]["url"]
                })

    liked_ids_set = set([i["videoId"] for i in liked_items])
    filtered = [
        song for song in results
        if "lyric" not in song["title"].lower()
        and "cover" not in song["title"].lower()
        and "instrumental" not in song["title"].lower()
        and song["videoId"] not in liked_ids_set
    ]
    return {"recommendations": filtered}

@router.get("/recently-played-details")
def get_recently_played(username: str = Depends(get_current_user)):
    with open(RECENT_PATH, "r") as f:
        data = json.load(f)
    items = data.get(username, [])
    results = []
    for item in items:
        video_id = item["videoId"]
        genre = item.get("genre", "unknown")
        params = {
            "part": "snippet",
            "id": video_id,
            "key": YOUTUBE_KEYS[current_key_index]
        }
        res = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params)
        res.raise_for_status()
        data = res.json()
        if data["items"]:
            snippet = data["items"][0]["snippet"]
            results.append({
                "title": snippet["title"],
                "channel": snippet["channelTitle"],
                "videoId": video_id,
                "thumbnail": snippet["thumbnails"]["high"]["url"],
                "genre": genre
            })
    return {"recently_played": results}

@router.get("/classify-genre/{video_id}")
def classify_genre(video_id: str):
    params = {
        "part": "snippet",
        "id": video_id,
        "maxResults": 1
    }
    data = make_youtube_request("https://www.googleapis.com/youtube/v3/videos", params)
    if not data["items"]:
        raise HTTPException(status_code=404, detail="Video not found")

    title = data["items"][0]["snippet"]["title"].lower()
    channel = data["items"][0]["snippet"]["channelTitle"].lower()
    text = f"{title} {channel}"

    for genre, keywords in GENRE_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            return {"genre": genre}
    return {"genre": "unknown"}


@router.get("/playlist/{mood}")
def generate_playlist(mood: str):
    return {"message": f"🎵 Playlist for mood: {mood}"}


@router.get("/genre/explore/{genre}")
def explore_by_genre(genre: str):
    keywords = GENRE_KEYWORDS.get(genre.lower())
    if not keywords:
        raise HTTPException(status_code=404, detail="Genre not found")

    results = []
    for keyword in keywords[:3]:
        params = {
            "part": "snippet",
            "q": keyword,
            "type": "video",
            "videoCategoryId": "10",
            "maxResults": 5
        }
        data = make_youtube_request("https://www.googleapis.com/youtube/v3/search", params)
        for item in data["items"]:
            if "videoId" not in item["id"]:
                continue

            title = item["snippet"]["title"].lower()
            channel = item["snippet"]["channelTitle"].lower()
            bad_keywords = ["interview", "reunites", "stream", "podcast", "live", "reaction", "clips", "ft.", "vs", "vs.", "debate"]
            bad_channels = ["adin", "live", "clips", "podcast"]
            if any(bad in title for bad in bad_keywords) or any(bad in channel for bad in bad_channels):
                continue

            results.append({
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "videoId": item["id"]["videoId"],
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                "genre": genre
            })
    return {"explore": results}


@router.get("/analytics")
def get_analytics(username: str = Depends(get_current_user)):
    try:
        with open("backend/data/analytics.json", "r") as f:
            data = json.load(f)
        return data.get(username, {"message": "No activity yet."})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load analytics: {str(e)}")












import requests
from fastapi import HTTPException
from backend import config

def get_youtube_key():
    if config.current_key_index >= len(config.YOUTUBE_KEYS):
        raise HTTPException(status_code=429, detail="All YouTube API keys exhausted.")
    return config.YOUTUBE_KEYS[config.current_key_index]

def rotate_youtube_key():
    config.current_key_index += 1
    if config.current_key_index >= len(config.YOUTUBE_KEYS):
        config.current_key_index = 0

def make_youtube_request(endpoint, params):
    for _ in range(len(config.YOUTUBE_KEYS)):
        key = get_youtube_key()
        params["key"] = key
        print(f"🔁 Using API key: {key}")

        try:
            res = requests.get(endpoint, params=params)
            print(f"➡️ Request URL: {res.url}")
            print(f"📄 Response Status: {res.status_code}")

            if res.status_code in [403, 400]:
                print(f"❌ Key failed, rotating...")
                rotate_youtube_key()
                continue

            res.raise_for_status()
            return res.json()

        except Exception as e:
            print(f"⚠️ API call failed: {e}")
            rotate_youtube_key()

    raise HTTPException(status_code=429, detail="All API keys failed")

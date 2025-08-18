# twitch_streamer.py
import os, requests
from urllib.parse import urlencode
from typing import List

BASE = "https://api.twitch.tv/helix"
OAUTH = "https://id.twitch.tv/oauth2/token"
CLIENT_ID = os.getenv("4lz42z4frmlvt13hb72ghrfi58ca84")
CLIENT_SECRET = os.getenv("m8w6m55deqh9mj1her3dos0y6odlyy")
APP_TOKEN = os.getenv("TWITCH_APP_TOKEN")
TIMEOUT = 10

def _get_app_token():
    global APP_TOKEN
    if APP_TOKEN:
        return APP_TOKEN
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET must be set.")
    r = requests.post(OAUTH, data={"client_id":CLIENT_ID,"client_secret":CLIENT_SECRET,"grant_type":"client_credentials"}, timeout=TIMEOUT)
    r.raise_for_status()
    APP_TOKEN = r.json()["access_token"]
    return APP_TOKEN

def _headers():
    return {"Client-ID": CLIENT_ID, "Authorization": f"Bearer {_get_app_token()}"}

def get_latest_vods_urls(login: str, max_videos: int = 5) -> List[str]:
    r = requests.get(f"{BASE}/users?{urlencode({'login':login})}", headers=_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json().get("data",[])
    if not data:
        return []
    uid = data[0]["id"]
    rv = requests.get(f"{BASE}/videos?{urlencode({'user_id':uid, 'type':'archive', 'first':max_videos})}", headers=_headers(), timeout=TIMEOUT)
    rv.raise_for_status()
    vids = rv.json().get("data",[])
    return [v.get("url") for v in vids if v.get("url")]



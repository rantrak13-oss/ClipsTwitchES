# twitch_streamer.py
import os, tempfile, subprocess, requests
from typing import List

BASE_URL = "https://api.twitch.tv/helix"
OAUTH_URL = "https://id.twitch.tv/oauth2/token"

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
MANUAL_TOKEN = os.getenv("TWITCH_APP_TOKEN")
REQ_TIMEOUT = 10.0

def _get_app_token():
    global MANUAL_TOKEN
    if MANUAL_TOKEN:
        return MANUAL_TOKEN
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("TWITCH_CLIENT_ID/TWITCH_CLIENT_SECRET no encontrados en entorno.")
    r = requests.post(OAUTH_URL, data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    MANUAL_TOKEN = r.json().get("access_token")
    return MANUAL_TOKEN

def _headers():
    token = _get_app_token()
    return {"Client-ID": CLIENT_ID, "Authorization": f"Bearer {token}"}

def obtener_urls_ultimos_directos(user_login: str, max_videos: int = 3) -> List[str]:
    r = requests.get(f"{BASE_URL}/users", headers=_headers(), params={"login": user_login}, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    data = r.json().get("data", [])
    if not data:
        return []
    user_id = data[0]["id"]
    rv = requests.get(f"{BASE_URL}/videos", headers=_headers(), params={"user_id": user_id, "type": "archive", "first": max_videos}, timeout=REQ_TIMEOUT)
    rv.raise_for_status()
    vids = rv.json().get("data", [])
    return [v.get("url") for v in vids if v.get("url")]

def descargar_vod_yt_dlp(url: str, out_dir: str = None, filename: str = None) -> str:
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="vod_")
    os.makedirs(out_dir, exist_ok=True)
    if filename:
        out_path = os.path.join(out_dir, filename)
    else:
        tmpf = tempfile.NamedTemporaryFile(delete=False, dir=out_dir, suffix=".mp4")
        out_path = tmpf.name
        tmpf.close()
    cmd = [
        "yt-dlp",
        "--no-part",
        "--no-mtime",
        "--quiet",
        "--retries", "3",
        "--socket-timeout", "15",
        "-f", "bestvideo+bestaudio/best",
        "-o", out_path,
        url
    ]
    subprocess.run(cmd, check=True)
    return out_path


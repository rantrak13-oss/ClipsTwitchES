# twitch_streamer.py
import os
import requests
import tempfile
import subprocess
from typing import List

BASE_URL = "https://api.twitch.tv/helix"
OAUTH_URL = "https://id.twitch.tv/oauth2/token"

CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
MANUAL_TOKEN = os.getenv("TWITCH_APP_TOKEN")  # opcional

REQ_TIMEOUT = 10.0

def _get_app_token() -> str:
    global MANUAL_TOKEN
    if MANUAL_TOKEN:
        return MANUAL_TOKEN
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("TWITCH_CLIENT_ID y TWITCH_CLIENT_SECRET deben estar en variables de entorno.")
    params = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    r = requests.post(OAUTH_URL, data=params, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    token = r.json().get("access_token")
    if not token:
        raise RuntimeError("No se pudo obtener token de Twitch.")
    MANUAL_TOKEN = token
    return token

def _headers():
    token = _get_app_token()
    return {"Client-ID": CLIENT_ID, "Authorization": f"Bearer {token}"}

def obtener_urls_ultimos_directos(user_login: str, max_videos: int = 3) -> List[str]:
    """Devuelve las URLs de los últimos VODs (archive) de user_login."""
    params = {"login": user_login}
    r = requests.get(f"{BASE_URL}/users", headers=_headers(), params=params, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    users = r.json().get("data", [])
    if not users:
        return []
    user_id = users[0]["id"]

    params_v = {"user_id": user_id, "type": "archive", "first": max_videos}
    rv = requests.get(f"{BASE_URL}/videos", headers=_headers(), params=params_v, timeout=REQ_TIMEOUT)
    rv.raise_for_status()
    videos = rv.json().get("data", [])
    urls = [v.get("url") for v in videos if v.get("url")]
    return urls

def descargar_vod_yt_dlp(url: str, out_dir: str = None, filename: str = None) -> str:
    """
    Descarga VOD via yt-dlp a archivo MP4. Devuelve la ruta local.
    """
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="vod_")
    os.makedirs(out_dir, exist_ok=True)
    if filename:
        out_path = os.path.join(out_dir, filename)
    else:
        tmp = tempfile.NamedTemporaryFile(delete=False, dir=out_dir, suffix=".mp4")
        out_path = tmp.name
        tmp.close()

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

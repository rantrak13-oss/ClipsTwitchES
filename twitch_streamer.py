import os
import time
import requests
from typing import List, Optional
from urllib.parse import urlencode
import subprocess
from pathlib import Path

API_BASE = "https://api.twitch.tv/helix"

def _get_app_token(client_id: str, client_secret: str) -> str:
    data = {"client_id": client_id, "client_secret": client_secret, "grant_type": "client_credentials"}
    r = requests.post("https://id.twitch.tv/oauth2/token", data=data, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]

def _headers(token: str, client_id: str):
    return {"Authorization": f"Bearer {token}", "Client-Id": client_id}

def get_vod_urls_by_login(login: str, client_id: str, client_secret: str,
                          app_token: Optional[str] = None, max_videos: int = 2) -> List[str]:
    token = app_token or _get_app_token(client_id, client_secret)
    # 1) get user id
    u = requests.get(f"{API_BASE}/users?{urlencode({'login': login})}",
                     headers=_headers(token, client_id), timeout=20).json()
    if not u.get("data"):
        return []
    user_id = u["data"][0]["id"]
    # 2) get videos (VODs)
    vids = requests.get(f"{API_BASE}/videos?{urlencode({'user_id': user_id, 'type': 'archive', 'first': max_videos})}",
                        headers=_headers(token, client_id), timeout=20).json()
    urls = [v["url"] for v in vids.get("data", []) if "url" in v]
    return urls

def download_vod_segmented(vod_url: str, output_mp4: Path):
    """
    Descarga progresiva usando yt-dlp → MP4 directamente en disco.
    Sin cargar el vídeo en RAM. Reintentos suaves para robustez.
    """
    output_mp4 = Path(output_mp4)
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    # Llamamos yt-dlp por subprocess para evitar overhead Python
    cmd = [
        "yt-dlp",
        "-o", str(output_mp4),
        "-f", "mp4",
        "--no-part",            # escribe directo, evita .part
        "--no-playlist",        # solo el vídeo
        "--retries", "10",
        "--fragment-retries", "10",
        "--concurrent-fragments", "4",
        vod_url
    ]
    tries = 0
    while tries < 3:
        try:
            subprocess.run(cmd, check=True)
            break
        except subprocess.CalledProcessError:
            tries += 1
            time.sleep(2 * tries)
    if not output_mp4.exists():
        raise RuntimeError(f"Fallo descargando VOD: {vod_url}")


# twitch_streamer.py
import os
import requests
import subprocess
import tempfile
import json
from typing import List

BASE_URL = "https://api.twitch.tv/helix"
OAUTH_URL = "https://id.twitch.tv/oauth2/token"

# Credenciales (poner en env vars del Space)
CLIENT_ID = os.getenv("4lz42z4frmlvt13hb72ghrfi58ca84")
CLIENT_SECRET = os.getenv("m8w6m55deqh9mj1her3dos0y6odlyy")
# Opcional: el usuario puede pasar un token manual en TWITCH_APP_TOKEN
APP_TOKEN = os.getenv("TWITCH_APP_TOKEN")

# timeouts
REQ_TIMEOUT = 10.0


def _get_app_token():
    """
    Obtiene token de app (client credentials grant). Guarda en memoria (no en disco).
    """
    global APP_TOKEN
    if APP_TOKEN:
        return APP_TOKEN

    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("TWITCH_CLIENT_ID y TWITCH_CLIENT_SECRET deben estar en las variables de entorno.")

    params = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials",
    }
    r = requests.post(OAUTH_URL, data=params, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    APP_TOKEN = data.get("access_token")
    if not APP_TOKEN:
        raise RuntimeError("No se pudo obtener token de Twitch (client credentials).")
    return APP_TOKEN


def _headers():
    token = _get_app_token()
    return {
        "Client-ID": CLIENT_ID,
        "Authorization": f"Bearer {token}"
    }


def obtener_urls_ultimos_directos(user_login: str, max_videos: int = 3) -> List[str]:
    """
    Devuelve lista de URLs (string) de los últimos VODs (archive) de un streamer.
    """
    # 1) obtener user id
    params = {"login": user_login}
    r = requests.get(f"{BASE_URL}/users", headers=_headers(), params=params, timeout=REQ_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if "data" not in data or not data["data"]:
        return []
    user_id = data["data"][0]["id"]

    # 2) obtener videos de tipo archive
    params_v = {"user_id": user_id, "type": "archive", "first": max_videos}
    rv = requests.get(f"{BASE_URL}/videos", headers=_headers(), params=params_v, timeout=REQ_TIMEOUT)
    rv.raise_for_status()
    dv = rv.json()
    if "data" not in dv or not dv["data"]:
        return []

    urls = []
    for v in dv["data"]:
        url = v.get("url")
        if url:
            urls.append(url)
    return urls


def descargar_vod(url: str, out_dir: str = None, filename: str = None) -> str:
    """
    Descarga el VOD con yt-dlp a un archivo mp4 temporal y devuelve la ruta.
    - out_dir: si se especifica, guarda allí; si no, usa temp dir.
    - filename: nombre del archivo (sin path). Si none, se genera con streamer+id.
    """
    if out_dir is None:
        out_dir = tempfile.mkdtemp(prefix="vod_")
    os.makedirs(out_dir, exist_ok=True)

    # Generación de nombre seguro
    if filename is None:
        # yt-dlp puede generar nombre por sí mismo, pero para control usamos temp file
        tmpf = tempfile.NamedTemporaryFile(delete=False, dir=out_dir, suffix=".mp4")
        tmpf.close()
        out_path = tmpf.name
    else:
        out_path = os.path.join(out_dir, filename)

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
    # Ejecutar y capturar errores
    subprocess.run(cmd, check=True)
    return out_path

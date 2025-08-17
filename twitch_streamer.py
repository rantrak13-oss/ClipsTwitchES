import os
import io
import asyncio
import tempfile
from pathlib import Path
import streamlink
from twitchAPI.twitch import Twitch
import inspect

# ============================================================
# Credenciales desde entorno (recomendado en Hugging Face > Settings > Secrets)
# ============================================================
CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "TU_CLIENT_ID")
CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "TU_CLIENT_SECRET")

# Crear cliente Twitch
twitch = Twitch(CLIENT_ID, CLIENT_SECRET)

# Autenticación tolerante (algunas versiones son sync, otras async)
try:
    maybe_coro = twitch.authenticate_app([])
    if inspect.isawaitable(maybe_coro):
        asyncio.get_event_loop().run_until_complete(maybe_coro)
except RuntimeError:
    # Si ya hay loop corriendo (poco frecuente en Streamlit), crea uno nuevo
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(maybe_coro)
except Exception:
    # Si era síncrono o ya estaba autenticado, seguimos
    pass


async def _resolve_result(obj):
    """Normaliza posibles respuestas de twitchAPI: dict, coroutine o async generator."""
    # Si es coroutine -> esperar resultado
    if inspect.isawaitable(obj):
        obj = await obj

    # Si es async generator -> convertir en lista de elementos
    if hasattr(obj, "__aiter__"):
        out = []
        async for item in obj:
            out.append(item)
        return out

    # Si es dict estándar -> devolver tal cual
    return obj


async def obtener_urls_ultimos_directos_async(user_login: str, max_videos: int = 3):
    """
    Devuelve lista de URLs de los últimos VODs (archives) del streamer.
    Soporta tanto twitchAPI síncrona como asíncrona bajo el capó.
    """
    res_user = await _resolve_result(twitch.get_users(logins=[user_login]))
    # Formato 1 (dict): {'data': [ {...} ]}
    if isinstance(res_user, dict):
        data = res_user.get("data", [])
    else:
        # Formato 2 (lista de elementos)
        data = res_user

    if not data:
        return []

    # Intentar extraer id del primer usuario
    user_id = None
    first = data[0]
    if isinstance(first, dict):
        user_id = first.get("id")
    else:
        # fallback por si el objeto es tipo-objeto con atributos
        user_id = getattr(first, "id", None)

    if not user_id:
        return []

    res_videos = await _resolve_result(
        twitch.get_videos(user_id=user_id, first=max_videos, type="archive")
    )

    urls = []
    if isinstance(res_videos, dict):
        for v in res_videos.get("data", []):
            url = v.get("url")
            if url:
                urls.append(url)
    else:
        # Lista de elementos; intentar atributo/clave 'url'
        for v in res_videos:
            url = v.get("url") if isinstance(v, dict) else getattr(v, "url", None)
            if url:
                urls.append(url)

    return urls


def obtener_urls_ultimos_directos(user_login: str, max_videos: int = 3):
    """Wrapper síncrono seguro (no revienta si hay event loop activo)."""
    try:
        return asyncio.run(obtener_urls_ultimos_directos_async(user_login, max_videos))
    except RuntimeError:
        # Si ya hay un loop en marcha (raro en Streamlit), reutilízalo
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Ejecuta en el loop existente
            fut = asyncio.ensure_future(obtener_urls_ultimos_directos_async(user_login, max_videos))
            return loop.run_until_complete(fut)
        return loop.run_until_complete(obtener_urls_ultimos_directos_async(user_login, max_videos))


def stream_vod_en_memoria(url: str) -> str:
    """
    Descarga el VOD de Twitch a un archivo temporal (formato .ts) usando streamlink
    y devuelve la RUTA del archivo. Es más estable y frugal que usar BytesIO con MoviePy.
    """
    streams = streamlink.streams(url)
    if not streams or "best" not in streams:
        raise RuntimeError("No se pudo obtener el stream 'best' con streamlink.")

    stream = streams["best"]
    fd = stream.open()

    # Archivo temporal .ts (Twitch VOD es HLS/TS, ffmpeg lo lee perfecto)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ts")
    tmp_path = tmp.name

    try:
        # Lee en chunks para no petar RAM
        while True:
            data = fd.read(1024 * 1024)  # 1 MB
            if not data:
                break
            tmp.write(data)
    finally:
        fd.close()
        tmp.close()

    return tmp_path

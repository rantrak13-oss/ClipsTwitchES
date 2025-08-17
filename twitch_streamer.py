import subprocess
import io
from twitchAPI.twitch import Twitch

TWITCH_APP_ID = "4lz42z4frmlvt13hb72ghrfi58ca84"
TWITCH_APP_SECRET = "m8w6m55deqh9mj1her3dos0y6odlyy"

twitch = Twitch(TWITCH_APP_ID, TWITCH_APP_SECRET)
twitch.authenticate_app([])

def obtener_urls_ultimos_directos(user_login, max_videos=3):
    """Devuelve las URLs de los últimos VODs de un streamer."""
    user_info = twitch.get_users(logins=[user_login])['data'][0]
    user_id = user_info['id']
    videos = twitch.get_videos(user_id=user_id, first=max_videos, type='archive')['data']
    return [v['url'] for v in videos]

def stream_vod_en_memoria(url):
    """
    Devuelve un objeto de VideoFileClip desde streaming (sin guardar en disco).
    """
    try:
        process = subprocess.Popen(
            ['streamlink', '--stdout', url, 'best'],
            stdout=subprocess.PIPE
        )
        return io.BytesIO(process.stdout.read())
    except Exception as e:
        print(f"Error en streaming VOD: {e}")
        return None

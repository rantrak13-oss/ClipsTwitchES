import os
from twitchAPI.twitch import Twitch

APP_ID = os.getenv("TWITCH_APP_ID")
APP_SECRET = os.getenv("TWITCH_APP_SECRET")
APP_TOKEN = os.getenv("TWITCH_APP_TOKEN")  # opcional

twitch = Twitch(APP_ID, APP_SECRET)
if APP_TOKEN:
    twitch.set_app_token(APP_TOKEN)
else:
    twitch.authenticate_app([])

def obtener_urls_ultimos_directos(user_login: str, max_videos: int = 3):
    """Devuelve una lista de URLs de los últimos directos de un streamer."""
    user_info = twitch.get_users(logins=[user_login])["data"]
    if not user_info:
        return []

    user_id = user_info[0]["id"]
    videos = twitch.get_videos(user_id=user_id, first=max_videos, type="archive")["data"]
    return [v["url"] for v in videos]

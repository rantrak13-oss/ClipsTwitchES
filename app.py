# app.py
import os
import shutil
import tempfile
import streamlit as st
from twitch_streamer import obtener_urls_ultimos_directos, descargar_vod_yt_dlp
from clip_selector import generate_final_mix
from utils import safe_remove_path

st.set_page_config(page_title="Twitch Hype Mixer", layout="wide")
st.title("🎬 Twitch Hype Mixer — Versión final")

# UI: streamers (default Spanish creators)
default_streamers = os.getenv("DEFAULT_STREAMERS", "Illojuan,ElXokas,Ibai,AuronPlay,TheGrefg")
streamers_input = st.text_input("Streamers (coma separados):", default_streamers)
streamers = [s.strip() for s in streamers_input.split(",") if s.strip()]

max_vods = st.number_input("VODs por streamer", min_value=1, max_value=5, value=2)
clip_length = st.slider("Duración por subclip (s)", 10, 120, 60)
top_n = st.slider("Top N subclips por VOD", 1, 5, 2)
whisper_choice = st.selectbox("Modelo Whisper (elige según RAM)", ["tiny", "base", "small"], index=2)
os.environ["WHISPER_MODEL"] = whisper_choice

if st.button("Generar mixes (un clip final por streamer)"):
    for streamer in streamers:
        st.write(f"🔎 Procesando {streamer} ...")
        try:
            urls = obtener_urls_ultimos_directos(streamer, max_videos=max_vods)
            if not urls:
                st.warning(f"No se encontraron VODs para {streamer}.")
                continue

            tmpdir = tempfile.mkdtemp(prefix=f"{streamer}_")
            local_vods = []
            try:
                # descargar VODs
                for i, url in enumerate(urls):
                    st.info(f"Descargando VOD {i+1}/{len(urls)}...")
                    path = descargar_vod_yt_dlp(url, out_dir=tmpdir, filename=f"{streamer}_{i}.mp4")
                    local_vods.append(path)

                st.info("Analizando VODs y generando subclips (esto puede tardar)...")
                final_path = generate_final_mix(local_vods, streamer, clip_length=clip_length, top_n_per_vod=top_n, max_total_seconds=3600)
                st.success(f"✅ Mix final generado: {final_path}")
                st.video(final_path)
                with open(final_path, "rb") as f:
                    st.download_button(f"Descargar {streamer}", data=f, file_name=os.path.basename(final_path))

            finally:
                # limpieza: elimina carpeta temporal con VODs y subclips
                safe_remove_path(tmpdir)

        except Exception as e:
            st.error(f"Error al procesar {streamer}: {e}")
            continue

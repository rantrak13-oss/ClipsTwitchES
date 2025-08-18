import os
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="🎬 Twitch Clip Agent", layout="wide")

st.title("🎬 Agente de Clips para Twitch (Optimizado)")
st.caption("CPU Basic (2 vCPU, 16GB RAM) • Descarga, analiza y mezcla clips de hasta 1h por streamer.")

# Variables de entorno (Twitch)
TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID", "")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET", "")
TWITCH_APP_TOKEN = os.getenv("TWITCH_APP_TOKEN", "")  # opcional

with st.expander("🔑 Credenciales Twitch (opcional si ya están en HF Secrets)"):
    TWITCH_CLIENT_ID = st.text_input("TWITCH_CLIENT_ID", TWITCH_CLIENT_ID, type="password")
    TWITCH_CLIENT_SECRET = st.text_input("TWITCH_CLIENT_SECRET", TWITCH_CLIENT_SECRET, type="password")
    TWITCH_APP_TOKEN = st.text_input("TWITCH_APP_TOKEN (opcional)", TWITCH_APP_TOKEN, type="password")

st.divider()

streamers_default = ["Illojuan", "ElXokas", "Ibai", "AuronPlay", "TheGrefg"]
streamers = st.tags(label="Añade streamers", text="Escribe y pulsa Enter", value=streamers_default)

max_vods = st.slider("¿Cuántos últimos directos por streamer analizar?", 1, 5, 2)
clip_max_h = st.slider("Duración máxima del mix por streamer (h)", 1, 3, 1)

col_a, col_b = st.columns(2)
with col_a:
    downscale = st.select_slider("Downscale vídeo (para análisis)", options=[1.0, 0.75, 0.5, 0.33, 0.25], value=0.5)
with col_b:
    frame_skip = st.select_slider("Frame skip (más alto = más rápido)", options=[1, 2, 3, 4, 5, 6, 8, 10], value=4)

out_dir = Path("/tmp/outputs")
out_dir.mkdir(parents=True, exist_ok=True)

# Estado de modelos (no se cargan hasta que hagan falta)
if "models_loaded" not in st.session_state:
    st.session_state["models_loaded"] = False

def lazy_load_models():
    if st.session_state["models_loaded"]:
        return
    with st.status("Cargando modelos (primera vez tarda más)...", expanded=True) as s:
        global whisper, pipeline
        import whisper
        from transformers import pipeline
        # Cargar whisper base (equilibrio calidad/CPU)
        st.write("• Cargando Whisper base…")
        st.session_state["whisper_model"] = whisper.load_model("base")  # en CPU
        # Sentimiento para texto (ligero)
        st.write("• Cargando pipeline de sentimiento…")
        st.session_state["sentiment"] = pipeline("sentiment-analysis")
        st.session_state["models_loaded"] = True
        s.update(label="Modelos listos ✅", state="complete")

def run_agent(streamers_list):
    # Imports pesados aquí (lazy)
    import tempfile
    from twitch_streamer import get_vod_urls_by_login, download_vod_segmented
    from audio_transcriber import transcribe_vod_by_chunks
    from video_scenes import detect_scenes_and_motion
    from hype_analyzer import score_hype_windows
    from clip_selector import select_and_render_mix

    results = []
    for login in streamers_list:
        with st.status(f"🔎 {login}: obteniendo VODs…", expanded=False):
            urls = get_vod_urls_by_login(
                login,
                client_id=TWITCH_CLIENT_ID,
                client_secret=TWITCH_CLIENT_SECRET,
                app_token=TWITCH_APP_TOKEN,
                max_videos=max_vods
            )

        if not urls:
            st.warning(f"No se encontraron VODs recientes para **{login}**.")
            continue

        # Trabajar en carpeta temporal por streamer
        with tempfile.TemporaryDirectory(prefix=f"{login}_") as td:
            work = Path(td)
            vod_paths = []
            for i, url in enumerate(urls, 1):
                st.write(f"⬇️ Descargando VOD {i}/{len(urls)} de {login} (descarga segmentada)…")
                mp4_path = work / f"vod_{i}.mp4"
                download_vod_segmented(url, mp4_path)  # descarga progresiva, disco, sin RAM
                vod_paths.append(mp4_path)

            # Audio + texto (Whisper por chunks + VAD)
            st.write("🗣️ Transcribiendo audio por bloques (con VAD)…")
            transcripts = []
            for mp4 in vod_paths:
                tr = transcribe_vod_by_chunks(mp4, st.session_state["whisper_model"])
                transcripts.append(tr)

            # Vídeo: escenas + movimiento (downscale + frame_skip)
            st.write("🎞️ Detectando escenas y movimiento…")
            video_signals = []
            for mp4 in vod_paths:
                sig = detect_scenes_and_motion(str(mp4), downscale=downscale, frame_skip=frame_skip)
                video_signals.append(sig)

            # Puntuar hype combinando señales
            st.write("⚡ Calculando hype (audio + texto + vídeo)…")
            hype_windows = score_hype_windows(
                transcripts=transcripts,
                video_signals=video_signals,
                window_s=30,  # ventanas cortas acumulan menos RAM
                sentiment_pipe=st.session_state["sentiment"]
            )

            # Selección y render del mix final (<= 1h)
            st.write("✂️ Seleccionando y renderizando mix final (FFmpeg, sin RAM)…")
            max_duration_s = clip_max_h * 3600
            out_mp4 = out_dir / f"{login}_mix.mp4"
            select_and_render_mix(
                vod_paths=[str(p) for p in vod_paths],
                hype_windows=hype_windows,
                max_total_duration_s=max_duration_s,
                output_path=str(out_mp4)
            )
            st.success(f"🎉 Mix listo para {login}")
            st.video(str(out_mp4))
            with open(out_mp4, "rb") as f:
                st.download_button("⬇️ Descargar MP4", f, file_name=out_mp4.name, mime="video/mp4")

            results.append(str(out_mp4))
    return results

# Botones
col1, col2 = st.columns([1,1])
with col1:
    if st.button("🚀 Cargar modelos", use_container_width=True):
        lazy_load_models()
        st.success("Modelos cargados en memoria.")
with col2:
    start = st.button("🎬 Analizar y generar clips", type="primary", use_container_width=True)

# Ejecución
if start:
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        st.error("Faltan credenciales de Twitch. Añádelas arriba o como Secrets en el Space.")
    else:
        if not st.session_state["models_loaded"]:
            lazy_load_models()
        _ = run_agent(streamers)

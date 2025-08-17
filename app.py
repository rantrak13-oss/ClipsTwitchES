# app.py
import os
import shutil
import streamlit as st
from twitch_streamer import obtener_urls_ultimos_directos, descargar_vod
from hype_analyzer import analizar_hype_combinado
from clip_selector import seleccionar_clips_from_scores
import tempfile

st.set_page_config(page_title="Twitch Hype Mixer - Final", layout="wide")
st.title("🎬 Twitch Hype Mixer — Versión Whisper integrada")

# Configuración
STREAMERS_DEFAULT = os.getenv("DEFAULT_STREAMERS", "Illojuan,ElXokas,Ibai,AuronPlay,TheGrefg")
streamers_input = st.text_input("Streamers (separados por coma)", STREAMERS_DEFAULT)
streamers = [s.strip() for s in streamers_input.split(",") if s.strip()]

max_vods = st.number_input("VODs por streamer", min_value=1, max_value=5, value=3)
clip_length = st.slider("Duración por subclip (s)", 10, 120, 60)
top_n = st.slider("Top N subclips por VOD", 1, 10, 5)
whisper_model = st.selectbox("Modelo Whisper (reduce si falta RAM)", ["tiny", "base", "small"], index=2)

# pass whisper model choice to env variable (affects analyzer)
os.environ["WHISPER_MODEL"] = whisper_model

if st.button("Generar mixes (1 clip final por streamer)"):
    for streamer in streamers:
        st.write(f"🔎 Procesando {streamer} ...")
        try:
            urls = obtener_urls_ultimos_directos(streamer, max_videos=max_vods)
            if not urls:
                st.warning(f"No se encontraron VODs para {streamer}.")
                continue

            submixes = []
            # temp dir to collect all final mixes per streamer
            final_tmpdir = tempfile.mkdtemp(prefix=f"{streamer}_")
            try:
                for i, url in enumerate(urls):
                    st.info(f"📥 Descargando VOD {i+1}/{len(urls)}: {url}")
                    vod_path = descargar_vod(url, out_dir=final_tmpdir, filename=f"{streamer}_{i}.mp4")
                    st.write("⏱ Analizando audio+transcripción...")
                    scores = analizar_hype_combinado(vod_path)
                    st.write("✂️ Seleccionando subclips...")
                    final_subclip = seleccionar_clips_from_scores(vod_path, scores, clip_length=clip_length, top_n=top_n)
                    if final_subclip:
                        submixes.append(final_subclip)
                if not submixes:
                    st.warning(f"No se generaron subclips para {streamer}.")
                    continue

                # concatenar submixes (cada submix ya es un archivo final de ese VOD)
                st.info("🔗 Concatenando submixes en mix final (máx 1h)...")
                from moviepy.editor import VideoFileClip, concatenate_videoclips
                clips_objs = [VideoFileClip(p) if isinstance(p, str) else p for p in submixes]
                mix = concatenate_videoclips(clips_objs, method="compose")
                if mix.duration > 3600:
                    mix = mix.subclip(0, 3600)
                out_final = os.path.join(final_tmpdir, f"{streamer}_mix_final.mp4")
                mix.write_videofile(out_final, codec="libx264", audio_codec="aac", verbose=False, logger=None)
                st.success(f"✅ Mix final generado para {streamer}")
                st.video(out_final)
                with open(out_final, "rb") as f:
                    st.download_button(f"Descargar {streamer}", data=f, file_name=os.path.basename(out_final))
            finally:
                # borra tempdir para no llenar disco (puedes comentar esta línea si quieres inspeccionar)
                try:
                    shutil.rmtree(final_tmpdir)
                except Exception:
                    pass

        except Exception as e:
            st.error(f"Error procesando {streamer}: {e}")
            continue


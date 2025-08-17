import streamlit as st
from twitch_streamer import obtener_urls_ultimos_directos, stream_vod_en_memoria
from hype_analyzer import analizar_hype
from clip_selector import seleccionar_clips
from moviepy.editor import concatenate_videoclips

st.set_page_config(page_title="Twitch Hype Mixer", layout="wide")
st.title("🎬 Twitch Hype Mixer - Mix automático de clips")

streamers_input = st.text_input("Introduce streamers separados por coma", 
                                "Illojuan,ElXokas,Ibai,AuronPlay,TheGrefg")
streamers = [s.strip() for s in streamers_input.split(",")]

clip_length = st.slider("Duración de cada clip (s)", 10, 120, 60)
top_n = st.slider("Número de clips por VOD", 1, 5)

if st.button("Generar mix final"):
    for streamer in streamers:
        st.write(f"Procesando {streamer}...")
        urls = obtener_urls_ultimos_directos(streamer, max_videos=3)
        clips_por_streamer = []

        for url in urls:
            st.write(f"Streaming VOD: {url}")
            vod_stream = stream_vod_en_memoria(url)
            if vod_stream is None:
                st.warning(f"No se pudo hacer streaming de {url}")
                continue

            try:
                scores = analizar_hype(vod_stream)
                clip = seleccionar_clips(vod_stream, scores, clip_length, top_n)
                if clip:
                    clips_por_streamer.append(clip)
            except Exception as e:
                st.warning(f"Error procesando VOD: {e}")
                continue

        if clips_por_streamer:
            final_mix = concatenate_videoclips(clips_por_streamer)
            if final_mix.duration > 3600:
                final_mix = final_mix.subclip(0, 3600)
            output_path = f"{streamer}_mix.mp4"
            final_mix.write_videofile(output_path, codec="libx264", audio_codec="aac")
            st.video(output_path)
            st.download_button("Descargar mix", data=open(output_path, "rb"), file_name=output_path)
        else:
            st.warning(f"No se generó mix para {streamer}")

import streamlit as st
import os

st.set_page_config(page_title="Clip Analyzer", layout="wide")

# Pantalla inicial rápida
st.title("🎬 Twitch Clip Analyzer")
st.write("Selecciona un streamer y genera un clip mix optimizado.")

# Lista de streamers
streamers = ["Illojuan", "ElXokas", "Ibai", "AuronPlay", "TheGrefg"]
selected_streamer = st.selectbox("Elige un streamer", streamers)

# Botón para analizar (no carga nada hasta que se pulse)
if st.button("Analizar último directo"):
    st.write(f"🔄 Analizando directos de **{selected_streamer}**...")

    # Importar librerías pesadas solo cuando se usan
    import torch
    import librosa
    import moviepy.editor as mp
    import whisper
    from transformers import pipeline

    # Cachear modelos pesados
    if "whisper_model" not in st.session_state:
        st.session_state["whisper_model"] = whisper.load_model("base")

    if "emotion_model" not in st.session_state:
        st.session_state["emotion_model"] = pipeline("sentiment-analysis")

    st.success("✅ Modelos cargados, iniciando análisis...")

    # Aquí vendría el análisis real con tu lógica
    # (placeholder para que no bloquee en el arranque)
    st.info(f"📊 Procesando VOD de {selected_streamer}... esto puede tardar unos minutos.")

    # Ejemplo de resultado
    st.video("https://www.w3schools.com/html/mov_bbb.mp4")

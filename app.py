import os
import gradio as gr
from twitchAPI.twitch import Twitch
import yt_dlp
from moviepy.editor import VideoFileClip, concatenate_videoclips
import cv2
import numpy as np
from fer import FER
import torch
from transformers import pipeline
import whisper

# -----------------------------
# CONFIGURACIÓN DE TWITCH
# -----------------------------
TWITCH_CLIENT_ID = "TU_CLIENT_ID"
TWITCH_CLIENT_SECRET = "TU_CLIENT_SECRET"
twitch = Twitch(TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)
twitch.authenticate_app([])

# -----------------------------
# FUNCIONES DE DESCARGA
# -----------------------------
def descargar_stream(url):
    output_path = "videos"
    os.makedirs(output_path, exist_ok=True)
    ydl_opts = {
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'format': 'bestvideo+bestaudio/best'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)
    return filepath

# -----------------------------
# FUNCIONES DE ANALISIS
# -----------------------------
# 1. Detección de emociones
def analizar_emociones(video_path):
    detector = FER(mtcnn=True)
    cap = cv2.VideoCapture(video_path)
    frames_with_hype = []
    frame_count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        result = detector.detect_emotions(frame)
        if result:
            for face in result:
                emotions = face["emotions"]
                if emotions["happy"] > 0.5 or emotions["surprise"] > 0.5:
                    frames_with_hype.append(frame_count)
    cap.release()
    return frames_with_hype

# 2. Transcripción de audio
def transcribir_audio(video_path):
    model = whisper.load_model("base")
    result = model.transcribe(video_path)
    return result["segments"]

# 3. Análisis de sentimiento
sentiment_pipeline = pipeline("sentiment-analysis")

def analizar_sentimiento(text_segments):
    hype_indices = []
    for seg in text_segments:
        score = sentiment_pipeline(seg["text"])[0]
        if score["label"] in ["POSITIVE"]:
            hype_indices.append(seg["start"])
    return hype_indices

# -----------------------------
# FUNCIÓN PRINCIPAL
# -----------------------------
def generar_clips(twitch_url):
    video_path = descargar_stream(twitch_url)
    
    # Analisis
    frames_hype = analizar_emociones(video_path)
    text_segments = transcribir_audio(video_path)
    text_hype = analizar_sentimiento(text_segments)
    
    # Combinamos señales simples (frames + texto)
    hype_times = sorted(set([f/30 for f in frames_hype] + text_hype))  # asumimos 30 fps
    
    # Cortar clips de max 1h
    clips = []
    video = VideoFileClip(video_path)
    start = 0
    max_duration = 3600  # 1h en segundos
    
    for t in hype_times:
        if t - start >= max_duration:
            clip = video.subclip(start, t)
            clip_path = f"clips/clip_{int(start)}_{int(t)}.mp4"
            os.makedirs("clips", exist_ok=True)
            clip.write_videofile(clip_path, codec="libx264", audio_codec="aac")
            clips.append(clip_path)
            start = t
    
    return clips

# -----------------------------
# INTERFAZ GRADIO
# -----------------------------
iface = gr.Interface(
    fn=generar_clips,
    inputs=gr.Textbox(label="URL del stream de Twitch"),
    outputs=gr.File(label="Clips generados"),
    title="Clipper Automático de Twitch",
    description="Analiza streams y genera clips de máximo 1h con los mejores momentos usando emociones, audio y texto."
)

iface.launch()


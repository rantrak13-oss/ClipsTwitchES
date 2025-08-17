import gradio as gr
from twitchAPI.twitch import Twitch
import os
from moviepy.editor import VideoFileClip, concatenate_videoclips
import cv2
import numpy as np
import torch
from transformers import pipeline
import whisper
from fer import FER

# --- CONFIGURACIÓN DE TWITCH ---
TWITCH_CLIENT_ID = "TU_CLIENT_ID"
TWITCH_CLIENT_SECRET = "TU_CLIENT_SECRET"
twitch = Twitch(TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET)
twitch.authenticate_app([])

# --- MODELOS ---
whisper_model = whisper.load_model("small")  # Transcripción
emotion_detector = FER(mtcnn=True)  # Detección de emociones
sentiment_pipeline = pipeline("sentiment-analysis")  # Análisis de texto

# --- FUNCIONES ---
def descargar_stream(video_url):
    """
    Descarga el stream completo usando yt-dlp
    """
    filename = "stream.mp4"
    os.system(f"yt-dlp -o {filename} {video_url}")
    return filename

def analizar_video(file_path):
    """
    Analiza el vídeo para detectar emociones y cambios de escena
    """
    clip = VideoFileClip(file_path)
    timestamps = []
    for t in np.arange(0, clip.duration, 2.0):  # cada 2 segundos
        frame = clip.get_frame(t)
        emotions = emotion_detector.detect_emotions(frame)
        if emotions:  # si detecta emoción fuerte
            timestamps.append(t)
    return timestamps

def transcribir_audio(file_path):
    """
    Transcribe audio y detecta frases virales / reacciones
    """
    result = whisper_model.transcribe(file_path)
    text_segments = []
    for seg in result["segments"]:
        sentiment = sentiment_pipeline(seg["text"])[0]
        if sentiment["label"] in ["POSITIVE", "NEGATIVE"]:
            text_segments.append((seg["start"], seg["end"]))
    return text_segments

def combinar_momentos(video_path, video_marks, audio_marks):
    """
    Combina señales de audio + video para elegir los clips
    """
    clip = VideoFileClip(video_path)
    final_clips = []
    for start in video_marks:
        for (a_start, a_end) in audio_marks:
            if a_start <= start <= a_end:
                end = min(start + 60*60, clip.duration)  # max 1h
                final_clips.append(clip.subclip(start, end))
                break
    if not final_clips:
        return None
    final_video = concatenate_videoclips(final_clips)
    output_file = "clips_generados.mp4"
    final_video.write_videofile(output_file, codec="libx264")
    return output_file

def generar_clips(video_url):
    """
    Función principal para generar clips
    """
    try:
        stream_file = descargar_stream(video_url)
        video_marks = analizar_video(stream_file)
        audio_marks = transcribir_audio(stream_file)
        output = combinar_momentos(stream_file, video_marks, audio_marks)
        if output:
            return output
        else:
            return "No se detectaron momentos relevantes."
    except Exception as e:
        return f"Error: {str(e)}"

# --- INTERFAZ GRADIO ---
iface = gr.Interface(
    fn=generar_clips,
    inputs=gr.Textbox(label="URL del stream de Twitch"),
    outputs=gr.File(label="Descargar clips generados"),
    title="Generador Avanzado de Clips de Twitch",
    description="Analiza streams, detecta los mejores momentos y genera clips de máximo 1 hora."
)

iface.launch()

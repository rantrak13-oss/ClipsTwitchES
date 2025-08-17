# hype_analyzer.py
import os
import numpy as np
import librosa
import torch
import whisper

# Modelo Whisper: configurable por env var
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
_device = "cuda" if torch.cuda.is_available() else "cpu"

_whisper_model = None
def _load_whisper():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model(WHISPER_MODEL, device=_device)
    return _whisper_model

def audio_rms(video_path: str, sr: int = 16000):
    try:
        y, sr = librosa.load(video_path, sr=sr, mono=True)
        hop_length = int(0.5 * sr)  # ventana ~0.5s
        frame_length = max(hop_length, 2048)
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        if rms.size == 0:
            return np.array([0.0])
        # normalizar 0-1
        if rms.max() > rms.min():
            rms = (rms - rms.min()) / (rms.max() - rms.min())
        else:
            rms = np.zeros_like(rms)
        return rms
    except Exception:
        return np.array([0.0])

def transcribe_whisper(video_path: str, language: str = None):
    model = _load_whisper()
    result = model.transcribe(video_path, language=language)
    return result.get("segments", [])

def combined_hype_score(video_path: str, keywords=None):
    """
    Devuelve un vector de scores (por frame window) combinando RMS + keyword boosts.
    """
    if keywords is None:
        keywords = ["wow","increible","increíble","hype","jajaja","jaja","lol","hostia","madre","epic","insane"]

    rms = audio_rms(video_path)
    M = len(rms)
    # tiempo total para mapear segments
    duration = librosa.get_duration(filename=video_path) if M>0 else 0.0
    times = np.linspace(0, duration, M) if M>0 else np.array([0.0])
    text_scores = np.zeros_like(rms)

    try:
        segs = transcribe_whisper(video_path)
        for seg in segs:
            s = seg.get("start", 0.0)
            e = seg.get("end", s + 1.0)
            txt = seg.get("text","").lower()
            boost = 0.0
            for kw in keywords:
                if kw in txt:
                    boost += 1.0
            if boost > 0:
                idx = np.where((times >= s) & (times <= e))[0]
                if idx.size>0:
                    text_scores[idx] += boost
    except Exception:
        # si falla la transcripcion, seguimos sólo con RMS
        text_scores = np.zeros_like(rms)

    # normalizar text_scores
    if text_scores.max() > text_scores.min():
        ts_norm = (text_scores - text_scores.min()) / (text_scores.max() - text_scores.min())
    else:
        ts_norm = np.zeros_like(text_scores)

    combined = rms + (ts_norm * 1.5)
    if combined.max() > combined.min():
        combined = (combined - combined.min()) / (combined.max() - combined.min())
    else:
        combined = np.zeros_like(combined)
    return combined



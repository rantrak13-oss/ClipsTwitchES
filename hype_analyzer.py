# hype_analyzer.py
import os
import tempfile
import numpy as np
import librosa
import torch
import whisper
from typing import List

# Cargar modelo Whisper al import (pero configurable via env)
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")  # tiny, base, small, medium...
_device = "cuda" if torch.cuda.is_available() else "cpu"

# Carga perezosa y cacheada para no recargar múltiples veces
_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model(WHISPER_MODEL, device=_device)
    return _whisper_model


def _transcribe_audio_from_video(video_path: str, language: str = None) -> List[dict]:
    """
    Transcribe using Whisper and return list of segments with start/end/text.
    """
    model = _get_whisper_model()
    result = model.transcribe(video_path, language=language)  # Whisper handles video input
    # result['segments'] exists when using standard whisper
    return result.get("segments", [])


def _audio_rms_scores(video_path: str, sr: int = 16000) -> np.ndarray:
    """
    Return normalized RMS scores per window (~0.5s frames).
    """
    try:
        y, sr = librosa.load(video_path, sr=sr, mono=True)
        hop_length = int(0.5 * sr)
        frame_length = max(hop_length, 2048)
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        if rms.size == 0:
            return np.array([0.0])
        # normalize 0-1
        if rms.max() > rms.min():
            rms = (rms - rms.min()) / (rms.max() - rms.min())
        else:
            rms = np.zeros_like(rms)
        return rms
    except Exception:
        return np.array([0.0])


def analizar_hype_combinado(video_path: str, keywords: List[str] = None):
    """
    Devuelve un vector de scores combinando:
    - RMS audio (energía)
    - Transcripción (presence of keywords -> boost)
    - (opcional) en el futuro: visual emotion detector
    """
    if keywords is None:
        keywords = ["wow", "increible", "increíble", "hype", "jajaja", "lol", "madre", "hostia", "insane"]

    # 1) RMS audio
    rms = _audio_rms_scores(video_path)  # array length M

    # 2) Transcribe and mark segments
    segments = _transcribe_audio_from_video(video_path)
    text_scores = np.zeros_like(rms)
    # Map segments into rms frames: determine time grid
    total_duration = max(0.0001, librosa.get_duration(filename=video_path))
    # times for rms
    M = len(rms)
    times = np.linspace(0, total_duration, M)
    for seg in segments:
        s = seg.get("start", 0.0)
        e = seg.get("end", s + 1.0)
        txt = seg.get("text", "").lower()
        boost = 0.0
        for kw in keywords:
            if kw in txt:
                boost += 1.0
        if boost > 0:
            # add boost to frames whose times are within [s,e]
            idxs = np.where((times >= s) & (times <= e))[0]
            if idxs.size > 0:
                text_scores[idxs] += boost

    # 3) Combine: normalized rms + scaled text_scores
    # normalize text_scores to 0-1
    if text_scores.max() > text_scores.min():
        ts_norm = (text_scores - text_scores.min()) / (text_scores.max() - text_scores.min())
    else:
        ts_norm = text_scores * 0.0

    # combine and normalize final
    combined = rms + (ts_norm * 1.5)  # give transcribed keyword higher weight
    if combined.max() > combined.min():
        combined = (combined - combined.min()) / (combined.max() - combined.min())
    return combined


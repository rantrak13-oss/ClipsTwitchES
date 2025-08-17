import os
import tempfile
import numpy as np
from pathlib import Path
from moviepy.editor import VideoFileClip, concatenate_videoclips

def _ensure_path(input_video) -> str:
    if isinstance(input_video, (str, os.PathLike)):
        return str(input_video)
    # Buffer -> archivo temporal
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ts")
    if hasattr(input_video, "read"):
        tmp.write(input_video.read())
    else:
        tmp.write(input_video)
    tmp.close()
    return tmp.name


def _nms_temporal(candidates, min_gap: float):
    """
    Supresión simple de no-máximos temporal: si dos inicios están muy cerca, nos quedamos
    con el que tenga score más alto. 'candidates' es lista de (start_sec, score).
    """
    # Ordenar por score descendente
    candidates = sorted(candidates, key=lambda x: x[1], reverse=True)
    selected = []
    for start, score in candidates:
        if all(abs(start - s0) >= min_gap for s0, _ in selected):
            selected.append((start, score))
    # Devolver orden cronológico
    return sorted(selected, key=lambda x: x[0])


def seleccionar_clips(video_input, scores, clip_length: float = 60.0, top_n: int = 10, min_gap: float = 30.0):
    """
    Selecciona los 'top_n' momentos con mayor score, evitando solapes cercanos (min_gap),
    y devuelve un VideoClip concatenado. Clips en orden cronológico.
    """
    video_path = _ensure_path(video_input)
    cap = VideoFileClip(video_path)
    duration = float(cap.duration)
    if duration <= 0:
        # Fallback: clip vacío controlado
        return cap.subclip(0, 0)

    # Paso temporal entre muestras de score
    step = duration / max(len(scores), 1)

    # Índices top por score (descendente)
    idx_sorted = np.argsort(scores)[::-1][:max(1, top_n)]
    # Pasar a candidatos (start_time, score)
    candidates = []
    for idx in idx_sorted:
        start = max(0.0, min(idx * step, max(0.0, duration - 1e-3)))
        candidates.append((start, float(scores[idx])))

    # No-Máximos temporal para evitar duplicados
    picks = _nms_temporal(candidates, min_gap=min_gap)
    if not picks:
        # Fallback: un clip desde el principio
        end = min(clip_length, duration)
        return cap.subclip(0, end)

    # Crear subclips ordenados y recortados dentro de los límites
    clips = []
    for start, _ in picks:
        end = min(start + clip_length, duration)
        if end > start:
            try:
                clips.append(cap.subclip(start, end))
            except Exception:
                # Si un subclip falla, lo saltamos
                pass

    if not clips:
        end = min(clip_length, duration)
        return cap.subclip(0, end)

    # Concatenación final; usar compose si hay tamaños/códecs distintos
    try:
        final = concatenate_videoclips(clips, method="compose")
    except Exception:
        final = concatenate_videoclips(clips)

    return final

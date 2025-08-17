# clip_selector.py
import os
import tempfile
import numpy as np
from moviepy.editor import VideoFileClip, concatenate_videoclips
from typing import List

def seleccionar_clips_from_scores(video_path: str, scores: np.ndarray, clip_length: float = 60.0, top_n: int = 10, min_gap: float = 30.0) -> str:
    """
    Selecciona top_n instantes por score, evita solapes (min_gap segundos),
    escribe cada subclip a disco temporal y concatena en un MP4 final.
    Devuelve ruta al archivo final.
    """
    cap = VideoFileClip(video_path)
    duration = cap.duration
    if duration <= 0:
        raise RuntimeError("Duración inválida del video.")

    step = duration / max(len(scores), 1)

    # Indices de top scores
    idxs = np.argsort(scores)[::-1][:max(1, top_n)]

    # Crear candidatos (start, score)
    candidates = [(max(0.0, min(idx * step, duration - 0.001)), float(scores[idx])) for idx in idxs]

    # NMS temporal simple
    selected = []
    for start, score in sorted(candidates, key=lambda x: x[1], reverse=True):
        if all(abs(start - s0) >= min_gap for s0, _ in selected):
            selected.append((start, score))
    # Orden cronológico
    selected = sorted(selected, key=lambda x: x[0])

    subclip_paths = []
    tmpdir = tempfile.mkdtemp(prefix="clips_")
    try:
        for i, (start, score) in enumerate(selected):
            end = min(start + clip_length, duration)
            if end <= start:
                continue
            out_path = os.path.join(tmpdir, f"clip_{i}.mp4")
            try:
                sub = cap.subclip(start, end)
                sub.write_videofile(out_path, codec="libx264", audio_codec="aac", verbose=False, logger=None)
                subclip_paths.append(out_path)
            except Exception:
                # saltar subclip si falla
                continue

        if not subclip_paths:
            # fallback: primer clip
            fallback = os.path.join(tmpdir, "fallback.mp4")
            cap.subclip(0, min(clip_length, duration)).write_videofile(fallback, codec="libx264", audio_codec="aac", verbose=False, logger=None)
            return fallback

        # Concatenate
        clips = [VideoFileClip(p) for p in subclip_paths]
        final_clip = concatenate_videoclips(clips, method="compose")
        final_path = os.path.join(tmpdir, "final_mix.mp4")
        # limit final duration to 1h if needed
        if final_clip.duration > 3600:
            final_clip = final_clip.subclip(0, 3600)
        final_clip.write_videofile(final_path, codec="libx264", audio_codec="aac", verbose=False, logger=None)
        return final_path
    finally:
        cap.close()
        # Note: no borro subclip files inmediatamente para evitar errores si se están usando,
        # app.py puede borrar tmpdir manualmente cuando haya terminado de servir el archivo.


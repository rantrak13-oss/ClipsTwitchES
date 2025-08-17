# clip_selector.py
import os
import tempfile
import numpy as np
from moviepy.editor import VideoFileClip, concatenate_videoclips
from hype_analyzer import combined_hype_score

def _select_top_times(scores, duration, top_n=5, min_gap=30.0):
    """Devuelve inicios (segundos) seleccionados, evitando solapes cercanos (min_gap)."""
    if len(scores)==0:
        return [0.0]
    idxs = np.argsort(scores)[::-1][:max(1, top_n)]
    step = duration / max(len(scores), 1)
    candidates = [(min(idx*step, max(0.0, duration-1e-3)), float(scores[idx])) for idx in idxs]
    # NMS temporal
    selected=[]
    for start, score in sorted(candidates, key=lambda x: x[1], reverse=True):
        if all(abs(start - s0) >= min_gap for s0, _ in selected):
            selected.append((start, score))
    selected = sorted(selected, key=lambda x: x[0])
    return [s for s,_ in selected]

def generate_final_mix(vod_paths, streamer_name, clip_length=60, top_n_per_vod=3, max_total_seconds=3600):
    """
    - vod_paths: lista de rutas locales de VODs
    - clip_length: segundos por subclip (ej. 60)
    - top_n_per_vod: cuántos subclips sacar por VOD (antes de NMS)
    - max_total_seconds: max duración final (3600s = 1h)
    Devuelve ruta al archivo final mix.
    """
    tmpdir = tempfile.mkdtemp(prefix=f"{streamer_name}_mix_")
    subclip_files = []

    for i, vod in enumerate(vod_paths):
        try:
            cap = VideoFileClip(vod)
            duration = cap.duration
            cap.reader.close()
            cap.audio.reader.close_proc() if cap.audio else None
        except Exception:
            duration = 0.0

        scores = combined_hype_score(vod)
        starts = _select_top_times(scores, duration, top_n=top_n_per_vod, min_gap=30.0)
        for j, start in enumerate(starts):
            end = min(start + clip_length, duration)
            if end <= start:
                continue
            out_path = os.path.join(tmpdir, f"{streamer_name}_v{ i }_c{ j }.mp4")
            try:
                v = VideoFileClip(vod).subclip(start, end)
                v.write_videofile(out_path, codec="libx264", audio_codec="aac", verbose=False, logger=None)
                subclip_files.append(out_path)
                v.close()
            except Exception:
                # saltar si falla
                continue

    if not subclip_files:
        raise RuntimeError("No se generaron subclips para concatenar.")

    # concatenar (en orden cronológico)
    clips = [VideoFileClip(p) for p in subclip_files]
    final = concatenate_videoclips(clips, method="compose")
    if final.duration > max_total_seconds:
        final = final.subclip(0, max_total_seconds)
    output_file = os.path.join(tmpdir, f"{streamer_name}_mix_final.mp4")
    final.write_videofile(output_file, codec="libx264", audio_codec="aac", verbose=False, logger=None)
    # cerrar clips
    final.close()
    for c in clips:
        c.close()
    return output_file


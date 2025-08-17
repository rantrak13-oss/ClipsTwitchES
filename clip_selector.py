import numpy as np
from moviepy.editor import VideoFileClip, concatenate_videoclips

def seleccionar_clips(video_path_or_file, scores, clip_length=60, top_n=10):
    """
    Selecciona los clips más hype de un VOD.
    Devuelve VideoFileClip concatenado.
    """
    try:
        cap = VideoFileClip(video_path_or_file)
    except:
        return None

    duration = cap.duration
    step = duration / max(len(scores), 1)
    clip_indices = np.argsort(scores)[-top_n:]
    clips = []

    for idx in clip_indices:
        start = min(idx * step, duration-1)
        end = min(start + clip_length, duration)
        try:
            clips.append(cap.subclip(start, end))
        except:
            continue

    if clips:
        return concatenate_videoclips(clips)
    else:
        return cap.subclip(0, min(clip_length, duration))

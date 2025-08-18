from typing import List, Dict, Tuple
import numpy as np
import re

VIRAL_PAT = re.compile(r"(jaja|jajaja|wtf|no puede ser|bro|madre m[ií]a|incre[ií]ble|qué locura|let's go|v[aá]monos|boom|hostia|tremendo)", re.IGNORECASE)
INSULT_PAT = re.compile(r"(tonto|idiota|imb[eé]cil|gilipollas|cabr[oó]n|mierda|asco|hater)", re.IGNORECASE)

def _aggregate_text_score(text: str, sentiment_pipe) -> float:
    # Sentimiento (rápido) + keywords
    base = 0.0
    if VIRAL_PAT.search(text):
        base += 0.6
    if INSULT_PAT.search(text):
        base += 0.4
    # Sentiment (positivo/negativo también puede ser hype)
    if text.strip():
        s = sentiment_pipe(text[:300])  # recorte para velocidad
        if s and isinstance(s, list):
            lab = s[0]["label"].lower()
            score = float(s[0]["score"])
            if "pos" in lab or "neg" in lab:
                base += 0.3 * score
    return min(1.0, base)

def score_hype_windows(transcripts: List[List[dict]],
                       video_signals: List[Dict],
                       window_s: int = 30,
                       sentiment_pipe=None) -> List[Tuple[float, float, float]]:
    """
    Combina múltiples VODs (transcripts + motion + scenes) en una línea temporal concatenada.
    Devuelve lista de ventanas (start, end, hype_score).
    """
    # Concatenar streams en una sola línea temporal
    windows = []
    t_offset = 0.0
    for tr, vs in zip(transcripts, video_signals):
        # Índices por ventana
        # Texto → agrupar por ventana
        if tr:
            t_end = max(x["end"] for x in tr)
        else:
            t_end = (vs["scenes"][-1][1] if vs["scenes"] else 0.0)
        total_s = max(t_end, (vs["motion"][-1][0] if vs["motion"] else 0.0))
        n_win = int(np.ceil(total_s / window_s))

        # Precompute motion median por ventana
        motion = vs.get("motion", [])
        motion_arr = np.zeros(n_win, dtype=np.float32)
        count_arr = np.zeros(n_win, dtype=np.int32)
        for t, m in motion:
            idx = int(t // window_s)
            if 0 <= idx < n_win:
                motion_arr[idx] += m
                count_arr[idx] += 1
        with np.errstate(divide='ignore', invalid='ignore'):
            motion_norm = np.where(count_arr > 0, motion_arr / np.maximum(count_arr, 1), 0.0)
            if motion_norm.max() > 0:
                motion_norm = motion_norm / motion_norm.max()

        # Texto y audio
        text_arr = np.zeros(n_win, dtype=np.float32)
        for seg in tr:
            idx = int(seg["start"] // window_s)
            if 0 <= idx < n_win:
                text_arr[idx] = max(text_arr[idx], _aggregate_text_score(seg["text"], sentiment_pipe))

        # Escenas: ventanas que caen cerca de cortes = +hype
        scene_bonus = np.zeros(n_win, dtype=np.float32)
        for s, e in vs.get("scenes", []):
            mid = 0.5*(s+e)
            idx = int(mid // window_s)
            for k in [idx-1, idx, idx+1]:
                if 0 <= k < n_win:
                    scene_bonus[k] += 0.15

        # Score final
        score = 0.55*text_arr + 0.35*motion_norm + 0.10*scene_bonus
        # Normalizar suave por VOD
        if score.max() > 0:
            score = score / score.max()

        # Exportar ventanas
        for i in range(n_win):
            s = t_offset + i*window_s
            e = t_offset + min((i+1)*window_s, total_s)
            windows.append((s, e, float(score[i])))
        t_offset += total_s
    return windows




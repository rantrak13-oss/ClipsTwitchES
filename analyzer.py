# analyzer.py
import os, math, tempfile
from pathlib import Path
from typing import List, Tuple, Dict
from faster_whisper import WhisperModel
import numpy as np
from utils_ffmpeg import ffprobe_duration, measure_volume_segment, cut_segment_copy
import cv2

# lazy model holder
_whisper = None
def get_whisper(model="tiny"):
    global _whisper
    if _whisper is None:
        # device cpu, compute_type int8 for speed
        _whisper = WhisperModel(model, device="cpu", compute_type="int8")
    return _whisper

# keyword lists
KEYWORDS = ["jaj", "jaja", "jajaj", "risas", "vamos", "vamos!", "increíble", "epic", "hype", "hostia", "brutal", "no puede ser","puta","puto","mierda"]

def text_score_simple(text: str) -> float:
    t = (text or "").lower()
    s = 0.0
    for kw in KEYWORDS:
        if kw in t:
            s += 1.0
    s += t.count("!") * 0.2
    s += t.count("jaj") * 0.5
    return s

def scene_change_score(media_path: str, start: float, end: float, sample_rate_hz: float = 1.0) -> float:
    # sample 1 fps (cheap) and measure hist diffs
    cap = cv2.VideoCapture(media_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, start*1000)
    last = None
    diffs = []
    t = start
    while t < end:
        ret, frame = cap.read()
        if not ret:
            break
        small = cv2.resize(frame, (160,90))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv],[0,1],None,[16,16],[0,180,0,256])
        hist = cv2.normalize(hist, hist).flatten()
        if last is not None:
            diffs.append(float(cv2.compareHist(last,hist,cv2.HISTCMP_BHATTACHARYYA)))
        last = hist
        # advance ~1s
        cap.set(cv2.CAP_PROP_POS_MSEC, (t+1.0)*1000)
        t += 1.0
    cap.release()
    return float(np.mean(diffs)) if diffs else 0.0

def transcribe_chunk(model, media_path: str, start: float, end: float) -> str:
    # use ffmpeg to cut chunk to temp file, transcribe, delete
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    cut_segment_copy(media_path, start, end, tmp.name)
    segments, _ = model.transcribe(tmp.name, beam_size=5)
    text = " ".join(s.text for s in segments)
    try:
        os.unlink(tmp.name)
    except:
        pass
    return text

def analyze_by_chunks(media_path: str, chunk_seconds: int = 300) -> List[Tuple[float,float,float]]:
    dur = ffprobe_duration(media_path)
    model = get_whisper()
    intervals = []
    n = math.ceil(dur / chunk_seconds)
    for i in range(n):
        s = i*chunk_seconds
        e = min(dur, s+chunk_seconds)
        vol_db = measure_volume_segment(media_path, s, e)  # -60..0 dB
        vol_score = max(0.0, (vol_db + 60.0) / 60.0)
        text = transcribe_chunk(model, media_path, s, e)
        text_score = text_score_simple(text)
        scene_s = scene_change_score(media_path, s, e)
        score = 1.2*vol_score + 1.5*text_score + 0.8*scene_s
        intervals.append((s, e, float(score)))
    return intervals





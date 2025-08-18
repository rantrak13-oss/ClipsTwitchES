# hype_analyzer.py
import os, tempfile, subprocess, numpy as np, librosa, torch
_whisper_model = None

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")
_device = "cuda" if torch.cuda.is_available() else "cpu"

def _load_whisper():
    global _whisper_model
    if _whisper_model is None:
        import whisper
        _whisper_model = whisper.load_model(WHISPER_MODEL, device=_device)
    return _whisper_model

def _extract_audio_ffmpeg(video_path: str, out_wav: str = None, sr: int = 16000):
    if out_wav is None:
        fd, out_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-ar", str(sr),
        "-ac", "1",
        "-f", "wav",
        out_wav
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_wav

def audio_rms(video_path: str, sr: int = 16000):
    wav = _extract_audio_ffmpeg(video_path, sr=sr)
    try:
        y, sr = librosa.load(wav, sr=sr, mono=True)
        hop = int(0.5 * sr)
        frame_length = max(hop, 2048)
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop)[0]
        if rms.size == 0:
            return np.array([0.0])
        if rms.max() > rms.min():
            rms = (rms - rms.min()) / (rms.max() - rms.min())
        else:
            rms = np.zeros_like(rms)
        return rms
    finally:
        try:
            os.remove(wav)
        except Exception:
            pass

def transcribe_whisper_segments(video_path: str, language: str = None):
    model = _load_whisper()
    # Whisper handles video path directly; segments returned contain start/end/text
    result = model.transcribe(video_path, language=language)
    return result.get("segments", [])

def combined_hype_score(video_path: str, keywords=None):
    if keywords is None:
        keywords = ["wow","increible","increíble","hype","jajaja","jaja","lol","hostia","madre","epic","insane"]
    rms = audio_rms(video_path)
    M = len(rms)
    duration = librosa.get_duration(filename=video_path) if M>0 else 0.0
    times = np.linspace(0, duration, M) if M>0 else np.array([0.0])
    text_scores = np.zeros_like(rms)
    try:
        segs = transcribe_whisper_segments(video_path)
        for seg in segs:
            s = seg.get("start", 0.0); e = seg.get("end", s+1.0); txt = seg.get("text","").lower()
            boost = sum(1.0 for kw in keywords if kw in txt)
            if boost > 0:
                idx = np.where((times >= s) & (times <= e))[0]
                if idx.size>0:
                    text_scores[idx] += boost
    except Exception:
        text_scores = np.zeros_like(rms)
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




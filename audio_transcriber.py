import subprocess
from pathlib import Path
import webrtcvad
import contextlib
import wave
import math
from typing import List, Dict

# Extrae audio PCM 16k mono por streaming (sin cargar vídeo)
def _extract_wav_pcm_16k(input_mp4: Path, out_wav: Path):
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_mp4),
        "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(out_wav)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _frame_generator(wav_path: Path, frame_ms=30):
    with contextlib.closing(wave.open(str(wav_path), 'rb')) as wf:
        sample_rate = wf.getframerate()
        frame_bytes = int(sample_rate * (frame_ms / 1000.0) * 2)  # 16-bit mono
        while True:
            data = wf.readframes(frame_bytes // 2)
            if len(data) < frame_bytes:
                break
            yield data, frame_ms

def _vad_timestamps(wav_path: Path, aggressiveness=2) -> List[Dict]:
    vad = webrtcvad.Vad(aggressiveness)
    ts = []
    cur_start = None
    t = 0.0
    for data, frame_ms in _frame_generator(wav_path):
        is_speech = vad.is_speech(data, 16000)
        if is_speech and cur_start is None:
            cur_start = t
        if not is_speech and cur_start is not None:
            ts.append({"start": cur_start, "end": t})
            cur_start = None
        t += frame_ms/1000.0
    if cur_start is not None:
        ts.append({"start": cur_start, "end": t})
    # Fusionar segmentos cercanos (<0.4s) y limitar a bloques cómodos (<=60s)
    merged = []
    for seg in ts:
        if not merged:
            merged.append(seg)
        else:
            if seg["start"] - merged[-1]["end"] <= 0.4:
                merged[-1]["end"] = seg["end"]
            else:
                merged.append(seg)
    # Trocear en sub-bloques <= 60s
    final = []
    for seg in merged:
        length = seg["end"] - seg["start"]
        if length <= 60:
            final.append(seg)
        else:
            # dividir en trozos de 55s con solape de 2s
            n = math.ceil(length / 55)
            for i in range(n):
                s = seg["start"] + i*55
                e = min(seg["end"], s+57)
                final.append({"start": s, "end": e})
    return final

def _extract_wav_slice(full_wav: Path, s: float, e: float, slice_wav: Path):
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{s:.2f}",
        "-to", f"{e:.2f}",
        "-i", str(full_wav),
        "-acodec", "pcm_s16le", "-ac", "1", "-ar", "16000",
        str(slice_wav)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def transcribe_vod_by_chunks(vod_mp4: Path, whisper_model) -> List[dict]:
    """
    Devuelve una lista de segmentos:
    [{start, end, text, conf_audio}], usando VAD para minimizar audio inútil.
    """
    vod_mp4 = Path(vod_mp4)
    work_wav = vod_mp4.with_suffix(".16k.wav")
    _extract_wav_pcm_16k(vod_mp4, work_wav)

    vad_segments = _vad_timestamps(work_wav, aggressiveness=2)
    results = []
    for seg in vad_segments:
        piece = work_wav.parent / f"slice_{seg['start']:.2f}_{seg['end']:.2f}.wav"
        _extract_wav_slice(work_wav, seg["start"], seg["end"], piece)
        tr = whisper_model.transcribe(str(piece), language="es", task="transcribe", verbose=False)
        # Guardar cada frase con timestamps relativos al VOD
        for s in tr.get("segments", []):
            results.append({
                "start": seg["start"] + s["start"],
                "end": seg["start"] + s["end"],
                "text": s.get("text", "").strip(),
                "conf_audio": float(tr.get("confidence", 0.0)) if "confidence" in tr else 0.0
            })
        try:
            piece.unlink(missing_ok=True)
        except Exception:
            pass

    try:
        work_wav.unlink(missing_ok=True)
    except Exception:
        pass
    return results

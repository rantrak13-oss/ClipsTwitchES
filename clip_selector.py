from typing import List, Tuple
from pathlib import Path
import subprocess
import heapq

def _ffmpeg_cut(src: str, start: float, end: float, out: str):
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-to", f"{end:.3f}",
        "-i", src,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        out
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _ffmpeg_concat_list(list_txt: Path, output_path: str):
    # concat demuxer sin re-encode (cuando codecs compatibles) o con re-encode del ejemplo
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_txt),
        "-c", "copy",
        output_path
    ]
    # Si falla por codecs, re-encode ligero:
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(list_txt),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def select_and_render_mix(vod_paths: List[str],
                          hype_windows: List[Tuple[float, float, float]],
                          max_total_duration_s: int,
                          output_path: str):
    """
    Selecciona las mejores ventanas (por score) hasta consumir <= max_total_duration_s (p.ej., 3600s),
    corta cada una directamente con FFmpeg (streaming en disco) y concatena en un único MP4.
    """
    # Top ventanas por score
    best = heapq.nlargest(500, hype_windows, key=lambda x: x[2])  # cap defensivo
    picked = []
    total = 0.0
    for s, e, sc in best:
        dur = e - s
        if dur <= 2.0:  # evitar segmentos ridículos
            continue
        if total + dur > max_total_duration_s:
            dur = max(0.0, max_total_duration_s - total)
            if dur < 2.0:
                break
            e = s + dur
        picked.append((s, e))
        total += dur
        if total >= max_total_duration_s:
            break

    # Cortar secuencialmente a ficheros temporales
    tmp_dir = Path(output_path).parent / (Path(output_path).stem + "_parts")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    # Mapear cada ventana al VOD correcto según offset acumulado
    # Aquí asumimos que hype_windows ya está en timeline concatenada del orden de vod_paths
    # Recalculamos offsets por VOD:
    import cv2
    offsets = []
    acc = 0.0
    for vp in vod_paths:
        cap = cv2.VideoCapture(vp)
        dur = (cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / (cap.get(cv2.CAP_PROP_FPS) or 30.0)
        cap.release()
        offsets.append((acc, acc + dur, vp))
        acc += dur

    def find_src(t_start: float, t_end: float):
        # Ventanas no cruzan VODs (porque vienen de ventanas de 30s); si cruzaran: se trocea en 2
        for a, b, vp in offsets:
            if a <= t_start < b:
                # clamp end
                t_s = max(0.0, t_start - a)
                t_e = max(0.0, min(t_end - a, b - a))
                return vp, t_s, t_e
        # fallback (raro)
        return offsets[-1][2], 0.0, max(0.0, t_end - offsets[-1][0])

    idx = 0
    for s, e in picked:
        src, ts, te = find_src(s, e)
        part = tmp_dir / f"part_{idx:04d}.mp4"
        _ffmpeg_cut(src, ts, te, str(part))
        parts.append(part)
        idx += 1

    # Crear lista concat
    list_txt = tmp_dir / "concat.txt"
    with open(list_txt, "w") as f:
        for p in parts:
            f.write(f"file '{p.as_posix()}'\n")

    _ffmpeg_concat_list(list_txt, output_path)

    # Limpieza opcional: comentar si quieres mantener trozos
    # for p in parts: p.unlink(missing_ok=True)
    # list_txt.unlink(missing_ok=True)
    # tmp_dir.rmdir()


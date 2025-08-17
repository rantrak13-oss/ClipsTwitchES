import os
import tempfile
import numpy as np
import librosa
from fer import FER
from moviepy.editor import VideoFileClip

def _ensure_path(input_video) -> str:
    """
    Acepta ruta o buffer (bytes/BytesIO). Si es buffer, vuelca a un archivo
    temporal y devuelve la ruta.
    """
    if isinstance(input_video, (str, os.PathLike)):
        return str(input_video)

    # Si es BytesIO o bytes -> volcar a .ts temporal
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ts")
    if hasattr(input_video, "read"):
        # file-like
        tmp.write(input_video.read())
    else:
        # bytes
        tmp.write(input_video)
    tmp.close()
    return tmp.name


def analizar_hype(video_input, max_visual_fps: float = 2.0):
    """
    Calcula un score de hype combinando emoción facial y RMS de audio.
    - Trabaja siempre por ruta (convierte buffers a archivo temporal).
    - Limita FPS de muestreo visual para ahorrar CPU/RAM.
    Devuelve: np.array de scores normalizados a la misma longitud.
    """
    video_path = _ensure_path(video_input)

    # Abrir video
    try:
        cap = VideoFileClip(video_path)
    except Exception as e:
        # Si falla el video, sin score
        return np.array([0.0], dtype=float)

    # FPS de muestreo visual (máximo 2 fps para no fundir la máquina)
    fps_native = cap.fps or 25
    sample_fps = min(max_visual_fps, float(fps_native))
    if sample_fps <= 0:
        sample_fps = 1.0

    # Detector de emociones (sin MTCNN para evitar dependencias extra)
    detector = FER(mtcnn=False)

    # --- VISUAL ---
    scores_visual = []
    try:
        for frame in cap.iter_frames(fps=sample_fps, dtype="uint8"):
            try:
                emotions = detector.detect_emotions(frame)
                if emotions:
                    # Tomamos la suma de probabilidades de la cara más "expresiva"
                    score = max(sum(face["emotions"].values()) for face in emotions)
                else:
                    score = 0.0
            except Exception:
                score = 0.0
            scores_visual.append(float(score))
    except Exception:
        # En caso de fallo del iterador de frames
        scores_visual = [0.0]

    scores_visual = np.asarray(scores_visual, dtype=float)
    if scores_visual.size == 0:
        scores_visual = np.array([0.0], dtype=float)

    # --- AUDIO ---
    # Cargamos audio con resample rápido para reducir uso de memoria
    try:
        y, sr = librosa.load(video_path, sr=16000, mono=True, res_type="kaiser_fast")
        # Ventanas de ~0.5s para RMS
        hop_length = int(0.5 * sr)
        frame_length = max(hop_length, 2048)
        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        # Normalización robusta
        if rms.size > 0 and rms.max() > rms.min():
            rms = (rms - rms.min()) / (rms.max() - rms.min())
        else:
            rms = np.zeros_like(rms)
    except Exception:
        rms = np.zeros( max(1, scores_visual.size), dtype=float )

    # --- Alineación ---
    # Igualamos longitudes por interpolación de la serie "más corta"
    L = max(scores_visual.size, rms.size)
    if scores_visual.size != L:
        x_old = np.linspace(0, 1, scores_visual.size)
        x_new = np.linspace(0, 1, L)
        scores_visual = np.interp(x_new, x_old, scores_visual)
    if rms.size != L:
        x_old = np.linspace(0, 1, rms.size)
        x_new = np.linspace(0, 1, L)
        rms = np.interp(x_new, x_old, rms)

    # --- Combinación ---
    combined = scores_visual.astype(float) + rms.astype(float)

    # Normalización final (evita explosiones)
    if combined.max() > combined.min():
        combined = (combined - combined.min()) / (combined.max() - combined.min())
    else:
        combined = np.zeros_like(combined)

    return combined

import numpy as np
import librosa
from fer import FER
from moviepy.editor import VideoFileClip

def analizar_hype(video_path_or_file):
    """
    Analiza hype combinando emoción visual y RMS de audio.
    Acepta path o BytesIO.
    """
    detector = FER(mtcnn=True)
    try:
        cap = VideoFileClip(video_path_or_file)
    except Exception as e:
        print(f"Error abriendo video: {e}")
        return np.array([0])

    fps = max(cap.fps, 1)
    duration = cap.duration
    scores_visual = []

    for frame in cap.iter_frames(fps=fps, dtype='uint8'):
        try:
            emotions = detector.detect_emotions(frame)
            score = max([sum(e['emotions'].values()) for e in emotions]) if emotions else 0
            scores_visual.append(score)
        except:
            scores_visual.append(0)

    try:
        y, sr = librosa.load(video_path_or_file, sr=None)
        rms = librosa.feature.rms(y=y)[0]
        rms = np.interp(rms, (rms.min(), rms.max()), (0, 1))
    except:
        rms = np.zeros(len(scores_visual))

    min_len = min(len(scores_visual), len(rms))
    return np.array(scores_visual[:min_len]) + np.array(rms[:min_len])

FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Sistema: ffmpeg (para moviepy/yt-dlp), libsndfile1 para librosa/soundfile
RUN apt-get update --allow-releaseinfo-change && apt-get install -y \
    ffmpeg \
    git \
    curl \
    build-essential \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar requirements y luego instalar (cacheo)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar código
COPY . /app

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

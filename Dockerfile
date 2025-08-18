# Dockerfile optimizado para CPU (Hugging Face CPU basic: 2 vCPU, 16GB)
FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Instalación de dependencias del sistema (ffmpeg, sonido, utilidades)
RUN apt-get update --allow-releaseinfo-change && \
    apt-get install -y --no-install-recommends \
      ffmpeg \
      libsndfile1 \
      wget \
      git \
      build-essential \
      ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiamos requirements.txt primero para cachear instalación
COPY requirements.txt /app/requirements.txt

# Instalamos pip y las dependencias; instalamos torch CPU wheel explícito
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir torch==2.0.1+cpu torchvision==0.15.2+cpu --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copiamos el resto del proyecto
COPY . /app

# Pre-cache modelos ligeros (opcional pero reduce latencia en primer uso)
# Cargamos whisper tiny (descarga durante build, ocupa algo de espacio pero acelera runtime)
RUN python - <<'PY'
try:
    import whisper, torch
    whisper.load_model("tiny")
except Exception as e:
    print("Precache whisper tiny failed:", e)
PY

# Exponer puerto Streamlit (usamos 8501)
EXPOSE 8501

# Variables para Streamlit headless
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ENABLECORS=false
ENV STREAMLIT_SERVER_ENABLEXsrfProtection=false

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]


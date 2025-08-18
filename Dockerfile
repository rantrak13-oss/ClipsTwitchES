FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PYTORCH_NO_CUDA_MEMORY_CACHING=1

# Dependencias del sistema mínimas
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Reqs primero para cachear
COPY requirements.txt .

# PyTorch CPU precompilado (rápido y sin compilar)
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    torch==2.0.1+cpu torchvision==0.15.2+cpu torchaudio==2.0.2+cpu

# Resto de deps
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY . .

# Puerto HF
ENV PORT=7860

# Streamlit headless y determinista
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]


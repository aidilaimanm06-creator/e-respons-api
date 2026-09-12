FROM python:3.11-slim

WORKDIR /app

# Install dependency sistem Linux untuk OpenCV
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-load/download model DeepFace siap-siap semasa BUILD gambar Docker
# Supaya server tak crash semasa terima request dari user
RUN python -c "from deepface import DeepFace; DeepFace.build_model('Emotion')"

COPY main.py .

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]

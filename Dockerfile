FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    opencv-data \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /usr/local/lib/python3.11/site-packages/cv2/data && \
    cp /usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml \
    /usr/local/lib/python3.11/site-packages/cv2/data/

COPY main.py .

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]

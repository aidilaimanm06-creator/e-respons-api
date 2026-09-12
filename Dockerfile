FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN pip uninstall -y opencv-python opencv-contrib-python opencv-contrib-python-headless || true

RUN pip install --no-cache-dir --force-reinstall opencv-python-headless==4.10.0.84

RUN python -c "import cv2; print('cv2:', cv2.__file__); print('version:', cv2.__version__); print('CascadeClassifier:', hasattr(cv2, 'CascadeClassifier')); print('haar:', cv2.data.haarcascades)"

COPY main.py .

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000}"]

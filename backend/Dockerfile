FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Tesseract OCR, PDF processing, and image handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Create thumbnails directory
RUN mkdir -p /app/shared/thumbnails

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "src.ingest.ingest_files"]

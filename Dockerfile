# Render will also build from just requirements.txt, but Dockerfile gives you control.
FROM python:3.11-slim

# Prevent Python from writing .pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System deps for pdfplumber (poppler-utils not required for text extraction)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg62-turbo-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py hf_client.py extractor.py ./

# Render provides $PORT env; bind to it
ENV PORT=10000
CMD exec gunicorn --bind 0.0.0.0:$PORT --workers 2 server:app

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    shared-mime-info \
    fonts-dejavu-core \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["sh", "-c", "gunicorn server:app --bind 0.0.0.0:${PORT:-8080} --workers 2 --worker-class uvicorn.workers.UvicornWorker --max-requests 1000 --max-requests-jitter 50 --access-logfile /dev/null --timeout 120"]

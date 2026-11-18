FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libopus0 ca-certificates curl xz-utils dpkg build-essential python3-dev git nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

CMD ["bash", "scripts/start.sh"]

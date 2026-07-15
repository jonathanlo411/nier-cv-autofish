FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt ./

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        linux-headers-amd64 \
        pkgconf \
        python3-dev \
        libgl1 \
        libglib2.0-0 \
        libglib2.0-dev \
        libc6-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-u", "app.py"]

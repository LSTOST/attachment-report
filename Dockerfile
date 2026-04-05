FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    libcairo2 \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p static/fonts \
    && wget -q -O static/fonts/NotoSansSC-Regular.otf \
        "https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/Chinese/NotoSansSC-Regular.otf" \
    && wget -q -O static/fonts/NotoSansSC-Bold.otf \
        "https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/Chinese/NotoSansSC-Bold.otf"

ENV PORT=8000
CMD sh -c 'uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"'

FROM python:3.12-slim

WORKDIR /app

# System libs: Pillow needs jpeg/png/webp; reportlab needs freetype for PDF text rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo \
    libpng16-16 \
    libwebp7 \
    zlib1g \
    libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Python deps first (layer caching — only re-runs when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .
RUN chmod +x /app/entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]

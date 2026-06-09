FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl gnupg ca-certificates \
    libnss3 libnspr4 \
    libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 \
    libexpat1 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 \
    libxkbcommon0 libx11-6 libx11-xcb1 \
    libxcb1 libxext6 libxfont2 \
    libxi6 libxtst6 libxss1 \
    libasound2 \
    fonts-liberation fonts-noto-color-emoji \
    xdg-utils \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar Chromium durante el BUILD (no al arrancar)
RUN playwright install chromium

COPY . .

# Usar script de inicio para que $PORT se expanda bien
CMD ["sh", "start.sh"]

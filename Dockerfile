FROM python:3.11-slim

# Dependencias del sistema para Chromium en Debian Trixie
# (playwright install-deps no soporta Trixie, instalamos manualmente)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core
    wget curl gnupg ca-certificates \
    # Chromium runtime libs
    libnss3 libnspr4 \
    libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 \
    libexpat1 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 \
    libxkbcommon0 libx11-6 libx11-xcb1 \
    libxcb1 libxext6 libxfont2 \
    libxi6 libxtst6 libxss1 \
    # Audio (dummy)
    libasound2 \
    # Fonts (paquetes disponibles en Trixie)
    fonts-liberation fonts-noto-color-emoji \
    # Misc
    xdg-utils \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar solo el binario de Chromium (sin install-deps)
RUN playwright install chromium

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]

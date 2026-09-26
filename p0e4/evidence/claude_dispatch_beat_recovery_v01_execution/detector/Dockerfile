FROM python:3.12-slim

# ffmpeg (incl. libfreetype voor drawtext) + curl (voor font-fetch tijdens build)
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Officiele OFL fonts voor de branded master (Cloud Build heeft internet) ---
# Cinzel SemiBold (wght 600) + Montserrat Regular (400) / Medium (500), geinstantieerd
# uit de officiele variable fonts. Faalt de download -> build faalt (geen stille fallback).
RUN mkdir -p /app/fonts && cd /app/fonts \
 && curl -fsSL -o Cinzel-var.ttf "https://github.com/google/fonts/raw/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf" \
 && curl -fsSL -o Montserrat-var.ttf "https://github.com/google/fonts/raw/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf" \
 && fonttools varLib.instancer -q Cinzel-var.ttf wght=600 -o Cinzel-SemiBold.ttf \
 && fonttools varLib.instancer -q Montserrat-var.ttf wght=400 -o Montserrat-Regular.ttf \
 && fonttools varLib.instancer -q Montserrat-var.ttf wght=500 -o Montserrat-Medium.ttf \
 && rm -f Cinzel-var.ttf Montserrat-var.ttf \
 && ls -la /app/fonts

COPY . .

ENV PORT=8080
# timeout 0: lange renders niet door gunicorn afkappen; Cloud Run bewaakt de max
CMD exec gunicorn --bind :$PORT --workers 2 --threads 4 --timeout 0 app:app

# --- ETAPA 1: Construcción del Frontend ---
FROM node:20 as build-step

WORKDIR /app
COPY package.json ./

# Limpieza y preparación
RUN rm -rf package-lock.json && npm cache clean --force
RUN npm install --legacy-peer-deps --no-audit

COPY . .
RUN npm run build

# --- ETAPA 2: Servidor (Python 3.11) ---
FROM python:3.11-slim

WORKDIR /app

# --- AQUÍ ESTÁ EL ARREGLO ---
# Instalamos ffmpeg (video) Y git (para descargar yt-dlp actualizado)
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Instalamos dependencias (Ahora sí funcionará git+https...)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el frontend construido en la Etapa 1
COPY --from=build-step /app/dist ./dist

# Copiamos el resto del código del servidor
COPY . .

# Variables
ENV FLASK_ENV=production
ENV PORT=5000

EXPOSE 5000

CMD ["python", "server.py"]

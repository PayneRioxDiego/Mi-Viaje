# --- ETAPA 1: Construcción del Frontend (Node.js) ---
FROM node:20 as build-step

WORKDIR /app

# Copiamos solo el package.json primero
COPY package.json ./

# Limpieza y preparación de entorno Node
# Borramos el package-lock.json si existe para evitar conflictos
RUN rm -rf package-lock.json && npm cache clean --force

# Instalación robusta (ignora versiones viejas y auditorías)
RUN npm install --legacy-peer-deps --no-audit

# Copiamos el resto del código
COPY . .

# Construimos la app (React -> carpeta dist)
RUN npm run build


# --- ETAPA 2: Servidor (Python ACTUALIZADO) ---
# CAMBIO IMPORTANTE: Usamos Python 3.10 para compatibilidad con Google Gemini
FROM python:3.10-slim

# Instalamos ffmpeg (necesario para yt-dlp)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

WORKDIR /app

# Copiamos requerimientos e instalamos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos la carpeta 'dist' construida en la Etapa 1
COPY --from=build-step /app/dist ./dist

# Copiamos el código del backend
COPY . .

# Variables de entorno
ENV FLASK_ENV=production
ENV PORT=5000

# Exponemos el puerto
EXPOSE 5000

# Arrancamos
CMD ["python", "server.py"]

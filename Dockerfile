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
# CAMBIO: Usamos 3.11 para estar al día y evitar warnings
FROM python:3.11-slim

# Instalamos ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

WORKDIR /app

# Instalamos dependencias (ahora con versiones fijas del requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo lo demás
COPY --from=build-step /app/dist ./dist
COPY . .

# Variables
ENV FLASK_ENV=production
ENV PORT=5000

EXPOSE 5000

# CAMBIO FINAL: Usamos Gunicorn en lugar de python directo
# Esto es mucho más robusto para producción y evita el "Exited Early"
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "server:app"]

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

# Instalamos ffmpeg (Necesario para procesar video)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

WORKDIR /app

# Instalamos dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo lo demás (incluido el frontend construido)
COPY --from=build-step /app/dist ./dist
COPY . .

# Variables
ENV FLASK_ENV=production
ENV PORT=5000

EXPOSE 5000

# --- CAMBIO CRÍTICO AQUÍ ---
# Usamos python directo para ahorrar memoria RAM y evitar error de dependencia
CMD ["python", "server.py"]

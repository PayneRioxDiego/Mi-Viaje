# --- ETAPA 1: Construcción (Node.js) ---
# CAMBIO 1: Subimos a Node 20 (versión más compatible con Vite nuevo)
FROM node:20 as build-step

WORKDIR /app

# Copiamos solo el package.json primero
COPY package.json ./

# CAMBIO 2: Estrategia de "Tierra Quemada"
# Borramos el package-lock.json si existe para evitar conflictos de versiones
# Limpiamos la caché de npm antes de empezar
RUN rm -rf package-lock.json && npm cache clean --force

# CAMBIO 3: Instalación robusta
# install: instala dependencias
# --legacy-peer-deps: ignora conflictos de pares
# --no-audit: no pierde tiempo buscando vulnerabilidades
RUN npm install --legacy-peer-deps --no-audit

# Copiamos el resto del código
COPY . .

# Construimos la app (React -> carpeta dist)
RUN npm run build


# --- ETAPA 2: Servidor (Python) ---
FROM python:3.9-slim

# Instalamos ffmpeg
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

# Variables de entorno para que Flask sepa que está en producción
ENV FLASK_ENV=production
ENV PORT=5000

# Exponemos el puerto
EXPOSE 5000

# Arrancamos
CMD ["python", "server.py"]

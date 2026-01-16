# --- ETAPA 1: Construir el Frontend (La parte bonita) ---
FROM node:18 as build-step

WORKDIR /app

# Copiamos los archivos de configuración
COPY package*.json ./

# --- AQUÍ ESTÁ EL CAMBIO CLAVE ---
# Agregamos '--legacy-peer-deps' para evitar errores de conflictos de versiones
# Agregamos '--no-audit' para que no pierda tiempo buscando vulnerabilidades ahora
RUN npm install --legacy-peer-deps --no-audit

# Copiamos todo el código fuente
COPY . .

# Construimos la carpeta 'dist'
RUN npm run build


# --- ETAPA 2: Configurar el Backend (Python) ---
FROM python:3.9-slim

# Instalamos ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

WORKDIR /app

# Copiamos requerimientos e instalamos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos la carpeta 'dist' generada en la etapa 1
COPY --from=build-step /app/dist ./dist

# Copiamos el código del backend
COPY . .

# Exponemos el puerto
EXPOSE 5000

# Arrancamos
CMD ["python", "server.py"]

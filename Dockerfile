# --- ETAPA 1: Construir el Frontend (La parte bonita) ---
# Usamos Node.js para "cocinar" (compilar) tu código React
FROM node:18 as build-step

WORKDIR /app

# Copiamos los archivos de configuración de Node
COPY package*.json ./

# Instalamos las dependencias de React (esto reemplaza a "npm install")
RUN npm install

# Copiamos todo el código fuente del frontend
COPY . .

# Construimos la carpeta 'dist' (esto reemplaza a "npm run build")
RUN npm run build


# --- ETAPA 2: Configurar el Backend (Python + Motor) ---
# Ahora usamos Python, igual que antes
FROM python:3.9-slim

# Instalamos ffmpeg (necesario para yt-dlp)
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean

WORKDIR /app

# Copiamos los requerimientos de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- AQUÍ ESTÁ EL TRUCO ---
# Copiamos la carpeta 'dist' que creamos en la Etapa 1
# y la pegamos dentro de la imagen de Python
COPY --from=build-step /app/dist ./dist

# Copiamos el resto del código (server.py, etc.)
COPY . .

# Exponemos el puerto
EXPOSE 5000

# Arrancamos el servidor (asegúrate que tu archivo se llame server.py)
CMD ["python", "server.py"]
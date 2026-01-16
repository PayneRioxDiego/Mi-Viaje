# 1. Usamos una imagen base de Python ligera (Linux)
FROM python:3.10-slim

# 2. INSTALACIÓN CRÍTICA: ffmpeg
# yt-dlp NECESITA ffmpeg para unir el video y el audio de TikTok correctamente.
# Sin esto, la descarga fallará o bajará videos mudos.
RUN apt-get update && \
    apt-get install -y ffmpeg git && \
    apt-get clean

# 3. Preparamos la carpeta de trabajo dentro del contenedor
WORKDIR /app

# 4. Copiamos primero los requerimientos (para aprovechar la caché de Docker)
COPY requirements.txt .

# 5. Instalamos las librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiamos el resto del código de tu app (app.py, etc.)
COPY . .

# 7. Exponemos el puerto (Flask suele usar el 5000 o el 8080)
EXPOSE 8080

# 8. El comando que arranca tu servidor
# Asegúrate de que tu archivo principal de Python se llame app.py o main.py
# Si se llama main.py, cambia "app.py" por "main.py" abajo.
CMD ["python", "server.py"]

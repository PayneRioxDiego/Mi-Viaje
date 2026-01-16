# Nuestro Viaje - Guía de Despliegue

Esta aplicación tiene dos partes: un Backend (Python) y un Frontend (React).

## 1. Conseguir API Key de Google Gemini
1. Ve a [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Crea una API Key.
3. Copiala, la necesitarás para los siguientes pasos.

## 2. Configurar GitHub
1. Crea un repositorio nuevo en GitHub.com.
2. Sube todos los archivos de esta carpeta a ese repositorio:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <TU_URL_DE_GITHUB>
   git push -u origin main
   ```

## 3. Desplegar Backend (Render.com)
Este servicio procesará los videos.
1. Crea cuenta en [Render.com](https://render.com).
2. Click en **"New + "** -> **"Web Service"**.
3. Conecta tu repositorio de GitHub.
4. Configuración:
   - **Runtime:** Docker
   - **Region:** Elige la más cercana (ej. Frankfurt o Oregon).
5. **Environment Variables** (Variables de Entorno):
   - Key: `API_KEY`
   - Value: (Pega tu clave de Gemini aquí)
6. Click en **Create Web Service**.
7. Espera a que termine. Copia la URL que te dan (ej: `https://mi-app.onrender.com`). **Esta es tu URL del Backend**.

## 4. Desplegar Frontend (Vercel)
Esta es la web que verás en tu celular.
1. Crea cuenta en [Vercel.com](https://vercel.com).
2. Click en **"Add New..."** -> **"Project"**.
3. Importa el mismo repositorio de GitHub.
4. **Environment Variables**:
   - Key: `VITE_API_URL`
   - Value: (Pega la URL de Render del paso anterior, sin la barra `/` al final)
   - Key: `VITE_GOOGLE_API_KEY`
   - Value: (Pega tu clave de Gemini aquí también para funciones locales)
5. Click en **Deploy**.

¡Listo! Vercel te dará un enlace (ej. `app-viajes.vercel.app`) que puedes abrir en tu móvil.

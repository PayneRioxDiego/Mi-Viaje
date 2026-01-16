import os
import time
import json
import glob
import tempfile
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp
import google.generativeai as genai
from dotenv import load_dotenv

# Load API Key
load_dotenv()
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    print("❌ ERROR: API_KEY not found in environment variables.")

# Configure Gemini
try:
    genai.configure(api_key=API_KEY)
except Exception as e:
    print(f"❌ Error configuring Gemini: {e}")

# Configurar Flask para servir la carpeta 'dist' (donde está React compilado)
# static_folder='dist' indica dónde están los archivos construidos
app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

def download_video(url):
    """Downloads video using yt-dlp to a temporary file."""
    print(f"⬇️ Iniciando descarga de: {url}")
    temp_dir = tempfile.mkdtemp()
    timestamp = int(time.time())
    output_template = os.path.join(temp_dir, f'video_{timestamp}.%(ext)s')

    ydl_opts = {
        'format': 'worst[ext=mp4]', 
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        files = glob.glob(os.path.join(temp_dir, 'video_*'))
        if files:
            print(f"✅ Video descargado en: {files[0]}")
            return files[0]
        return None
    except Exception as e:
        print(f"❌ Download Error: {e}")
        return None

def analyze_with_gemini(video_path):
    """Uploads video to Gemini and analyzes it."""
    print(f"📤 Subiendo {video_path} a Gemini...")
    
    try:
        video_file = genai.upload_file(path=video_path)
    except Exception as e:
        raise Exception(f"Fallo al subir a Gemini: {e}")
    
    print("⏳ Esperando procesamiento de video en la nube...")
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name == "FAILED":
        raise Exception("Video processing failed.")

    print("🤖 Video listo. Generando análisis con IA...")

    model = genai.GenerativeModel(model_name="gemini-2.5-flash")
    
    prompt = """
    Actúa como un crítico de viajes escéptico y profesional. Analiza el video buscando inconsistencias.
    
    Extrae la información en formato JSON estricto:
    {
      "category": "Lugar" | "Comida" | "Actividad" | "Consejo" | "Otro",
      "placeName": "Nombre exacto",
      "estimatedLocation": "Ciudad, País",
      "priceRange": "Precio estimado",
      "summary": "Resumen de 1 frase",
      "score": 1-5 (Integer),
      "confidenceLevel": "Alto" | "Medio" | "Bajo",
      "criticalVerdict": "Justificación escéptica corta",
      "isTouristTrap": boolean
    }
    """

    response = model.generate_content(
        [video_file, prompt],
        generation_config={
            "response_mime_type": "application/json"
        }
    )

    try:
        genai.delete_file(video_file.name)
    except:
        pass
    
    return json.loads(response.text)

# --- RUTAS DE API ---

@app.route('/analyze', methods=['POST'])
def analyze_video():
    print("🔔 Petición recibida en /analyze")
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    print(f"🔍 Procesando URL: {url}")
    
    video_path = None
    try:
        # 1. Download
        video_path = download_video(url)
        if not video_path:
            return jsonify({"error": "Fallo al descargar el video."}), 500

        # 2. Analyze
        analysis_result = analyze_with_gemini(video_path)
        return jsonify(analysis_result)

    except Exception as e:
        print(f"❌ Error en servidor: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)

@app.route('/health', methods=['GET'])
def health_check():
    return "Backend operativo", 200

# --- SIRVIENDO REACT ---
# Esta ruta captura cualquier URL que no sea API y devuelve el index.html
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Servidor Todo-en-Uno LISTO en puerto {port}")
    app.run(host='0.0.0.0', port=port)
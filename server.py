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
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Load Environment Variables
load_dotenv()
API_KEY = os.getenv("API_KEY") 

# --- GOOGLE SHEETS SETUP ---
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive"]

def get_db_connection():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    if not creds_json or not sheet_id:
        print("⚠️ Google Sheets no configurado. Usando memoria local.")
        return None

    try:
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        return sheet
    except Exception as e:
        print(f"❌ Error conectando a Google Sheets: {e}")
        return None

# --- GEMINI SETUP ---
if not API_KEY:
    print("❌ ERROR: API_KEY not found in environment variables.")

try:
    genai.configure(api_key=API_KEY)
except Exception as e:
    print(f"❌ Error configuring Gemini: {e}")

# --- FLASK SETUP ---
app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

LOCAL_DB = []

# --- HELPER FUNCTIONS ---
def download_video(url):
    print(f"⬇️ Iniciando descarga de: {url}")
    temp_dir = tempfile.mkdtemp()
    timestamp = int(time.time())
    output_template = os.path.join(temp_dir, f'video_{timestamp}.%(ext)s')

    # CONFIGURACIÓN OPTIMIZADA (MODO IPHONE)
    ydl_opts = {
        'format': 'worst[ext=mp4]', 
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        'http_headers': {
            'Referer': 'https://www.tiktok.com/',
            'Accept-Language': 'en-US,en;q=0.9',
        },
        'source_address': '0.0.0.0', 
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
        generation_config={"response_mime_type": "application/json"}
    )

    try:
        genai.delete_file(video_file.name)
    except:
        pass
    
    raw_data = json.loads(response.text)

    # --- FIX LISTAS (AQUÍ ESTÁ LA MAGIA) ---
    # Si Gemini nos da una lista [{...}], sacamos el diccionario de adentro.
    if isinstance(raw_data, list):
        print("⚠️ Gemini devolvió una lista, extrayendo primer elemento...")
        if len(raw_data) > 0:
            raw_data = raw_data[0]
        else:
            raw_data = {} # Lista vacía, prevenimos error

    # --- BLOQUE DE SEGURIDAD (SANITIZACIÓN) ---
    safe_data = {
        "category": raw_data.get("category") or "Otro",
        "placeName": raw_data.get("placeName") or "Lugar Desconocido",
        "estimatedLocation": raw_data.get("estimatedLocation") or "Ubicación no encontrada",
        "priceRange": raw_data.get("priceRange") or "Precio desconocido",
        "summary": raw_data.get("summary") or "No se pudo generar resumen.",
        "score": raw_data.get("score") or 0,
        "confidenceLevel": raw_data.get("confidenceLevel") or "Bajo",
        "criticalVerdict": raw_data.get("criticalVerdict") or "Sin veredicto",
        "isTouristTrap": raw_data.get("isTouristTrap") if raw_data.get("isTouristTrap") is not None else False
    }

    print("✅ Datos enviados al frontend:", safe_data)
    return safe_data

# --- API ROUTES ---

@app.route('/analyze', methods=['POST'])
def analyze_video():
    print("🔔 Petición recibida en /analyze")
    data = request.json
    
    # FIX EXTRA: Si el frontend envía una lista por error, tomamos el primer item
    if isinstance(data, list):
        data = data[0]

    url = data.get('url')

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    video_path = None
    try:
        video_path = download_video(url)
        if not video_path:
            return jsonify({"error": "Fallo al descargar el video."}), 500

        analysis_result = analyze_with_gemini(video_path)
        return jsonify(analysis_result)

    except Exception as e:
        print(f"❌ Error en servidor: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)

@app.route('/api/history', methods=['GET'])
def get_history():
    sheet = get_db_connection()
    if sheet:
        try:
            records = sheet.get_all_records()
            return jsonify(records)
        except Exception as e:
            print(f"Error leyendo Sheets: {e}")
            return jsonify(LOCAL_DB)
    else:
        return jsonify(LOCAL_DB)

@app.route('/api/history', methods=['POST'])
def save_history():
    data = request.json
    sheet = get_db_connection()
    
    if sheet:
        try:
            row = [
                data.get('id'),
                data.get('timestamp'),
                data.get('placeName'),
                data.get('category'),
                data.get('score'),
                data.get('estimatedLocation'),
                data.get('summary'),
                data.get('fileName')
            ]
            sheet.append_row(row)
            return jsonify({"status": "saved to cloud", "data": data})
        except Exception as e:
            print(f"Error guardando en Sheets: {e}")
            LOCAL_DB.append(data)
            return jsonify({"status": "saved to local memory fallback", "data": data})
    else:
        LOCAL_DB.append(data)
        return jsonify({"status": "saved to local memory", "data": data})

@app.route('/health', methods=['GET'])
def health_check():
    return "Backend operativo", 200

# --- STATIC FILES ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

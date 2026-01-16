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

# --- CONFIGURACIÓN INICIAL ---
load_dotenv()
API_KEY = os.getenv("API_KEY")

# Configuración de Gemini
if not API_KEY:
    print("❌ ERROR: API_KEY not found.")
try:
    genai.configure(api_key=API_KEY)
except Exception as e:
    print(f"❌ Error Gemini: {e}")

# Configuración Flask
app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# Memoria Local (Fallback)
LOCAL_DB = []

# --- CONEXIÓN A SHEETS ---
def get_db_connection():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    
    if not creds_json or not sheet_id:
        return None

    try:
        creds_dict = json.loads(creds_json)
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).sheet1
        return sheet
    except Exception as e:
        print(f"❌ Error Sheets: {e}")
        return None

# --- DESCARGA DE VIDEO ---
def download_video(url):
    print(f"⬇️ Descargando: {url}")
    temp_dir = tempfile.mkdtemp()
    timestamp = int(time.time())
    output_template = os.path.join(temp_dir, f'video_{timestamp}.%(ext)s')

    ydl_opts = {
        'format': 'worst[ext=mp4]', 
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        'http_headers': {'Referer': 'https://www.tiktok.com/'},
        'source_address': '0.0.0.0', 
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        files = glob.glob(os.path.join(temp_dir, 'video_*'))
        if files: return files[0]
        return None
    except Exception as e:
        print(f"❌ Error descarga: {e}")
        return None

# --- ANÁLISIS GEMINI ---
def analyze_with_gemini(video_path):
    print(f"📤 Subiendo a Gemini...")
    try:
        video_file = genai.upload_file(path=video_path)
    except Exception as e:
        raise Exception(f"Fallo subida: {e}")
    
    while video_file.state.name == "PROCESSING":
        time.sleep(1)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name == "FAILED":
        raise Exception("Procesamiento fallido.")

    print("🤖 Analizando...")
    model = genai.GenerativeModel(model_name="gemini-2.5-flash")
    
    prompt = """
    Analiza el video. Devuelve JSON estricto:
    {
      "category": "Lugar/Comida/Otro",
      "placeName": "Nombre",
      "estimatedLocation": "Ciudad",
      "priceRange": "Precio",
      "summary": "Resumen",
      "score": 0,
      "confidenceLevel": "Alto",
      "criticalVerdict": "Opinion",
      "isTouristTrap": false
    }
    """

    response = model.generate_content(
        [video_file, prompt],
        generation_config={"response_mime_type": "application/json"}
    )

    try: genai.delete_file(video_file.name)
    except: pass
    
    raw_data = json.loads(response.text)

    # Corrección de listas
    if isinstance(raw_data, list):
        raw_data = raw_data[0] if len(raw_data) > 0 else {}

    # Sanitización
    safe_data = {
        "category": str(raw_data.get("category") or "Otro"),
        "placeName": str(raw_data.get("placeName") or "Desconocido"),
        "estimatedLocation": str(raw_data.get("estimatedLocation") or "No encontrada"),
        "priceRange": str(raw_data.get("priceRange") or "??"),
        "summary": str(raw_data.get("summary") or "Sin resumen"),
        "score": raw_data.get("score") or 0,
        "confidenceLevel": str(raw_data.get("confidenceLevel") or "Bajo"),
        "criticalVerdict": str(raw_data.get("criticalVerdict") or "Sin veredicto"),
        "isTouristTrap": bool(raw_data.get("isTouristTrap"))
    }
    return safe_data

# --- RUTAS ---

@app.route('/analyze', methods=['POST'])
def analyze_video():
    data = request.json
    if isinstance(data, list): data = data[0]

    url = data.get('url')
    if not url: return jsonify({"error": "No URL"}), 400

    video_path = download_video(url)
    if not video_path: return jsonify({"error": "Error descarga"}), 500

    try:
        result = analyze_with_gemini(video_path)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)

@app.route('/api/history', methods=['GET'])
def get_history():
    sheet = get_db_connection()
    raw_records = []
    
    if sheet:
        try: raw_records = sheet.get_all_records()
        except: raw_records = LOCAL_DB
    else:
        raw_records = LOCAL_DB

    # LIMPIEZA ANTI-CRASH
    clean_records = []
    for record in raw_records:
        if not isinstance(record, dict): continue
        safe_record = {
            "id": str(record.get("id") or ""),
            "timestamp": record.get("timestamp") or 0,
            "placeName": str(record.get("placeName") or "Desconocido"),
            "category": str(record.get("category") or "Otro"), 
            "score": record.get("score") or 0,
            "estimatedLocation": str(record.get("estimatedLocation") or ""),
            "summary": str(record.get("summary") or ""),
            "fileName": str(record.get("fileName") or ""),
            "confidenceLevel": str(record.get("confidenceLevel") or "Bajo")
        }
        clean_records.append(safe_record)

    return jsonify(clean_records)

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
            return jsonify({"status": "saved"})
        except:
            LOCAL_DB.append(data)
            return jsonify({"status": "fallback"})
    else:
        LOCAL_DB.append(data)
        return jsonify({"status": "local"})

@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

# Archivos estáticos
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

# --- ARRANQUE DEL SERVIDOR ---
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

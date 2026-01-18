import os
import time
import json
import glob
import tempfile
import uuid
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp
import google.generativeai as genai
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURACIÓN ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Gemini
if not API_KEY: print("❌ ERROR: API_KEY not found.")
try: genai.configure(api_key=API_KEY)
except Exception as e: print(f"❌ Error Gemini: {e}")

# Flask
app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# Memoria Local
LOCAL_DB = []

# --- GOOGLE SHEETS ---
def get_db_connection():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not creds_json or not sheet_id: return None
    try:
        creds_dict = json.loads(creds_json)
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
        client = gspread.authorize(creds)
        return client.open_by_key(sheet_id).sheet1
    except Exception as e:
        print(f"❌ Error Sheets: {e}")
        return None

# --- VERIFICACIÓN CON MAPS ---
def verify_location_with_maps(place_name, location_hint):
    if not MAPS_API_KEY: return None
    print(f"🗺️ Verificando: {place_name}...")
    
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.id,places.location"
    }
    query = f"{place_name} {location_hint}"
    payload = {"textQuery": query}

    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        if "places" in data and len(data["places"]) > 0:
            best = data["places"][0]
            print(f"✅ Encontrado: {best.get('displayName', {}).get('text')}")
            return {
                "officialName": best.get("displayName", {}).get("text"),
                "address": best.get("formattedAddress"),
                "placeId": best.get("id"),
                "lat": best.get("location", {}).get("latitude"),
                "lng": best.get("location", {}).get("longitude")
            }
    except: pass
    return None

# --- DESCARGA ---
def download_video(url):
    print(f"⬇️ Descargando: {url}")
    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, f'video_{int(time.time())}.%(ext)s')
    ydl_opts = {
        'format': 'worst[ext=mp4]', 
        'outtmpl': output_template,
        'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        'http_headers': {'Referer': 'https://www.tiktok.com/'},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        files = glob.glob(os.path.join(temp_dir, 'video_*'))
        return files[0] if files else None
    except Exception as e:
        return None

# --- ANÁLISIS MULTI-LUGAR ---
def analyze_with_gemini(video_path):
    print(f"📤 Subiendo a Gemini...")
    try:
        video_file = genai.upload_file(path=video_path)
        while video_file.state.name == "PROCESSING":
            time.sleep(1)
            video_file = genai.get_file(video_file.name)
    except Exception as e:
        raise Exception(f"Error Gemini: {e}")

    print("🤖 Analizando múltiples lugares...")
    try: model = genai.GenerativeModel(model_name="gemini-2.5-flash")
    except: model = genai.GenerativeModel(model_name="gemini-pro")
    
    # PROMPT ACTUALIZADO PARA LISTAS
    prompt = """
    Analiza este video de viaje. Identifica TODOS los lugares turísticos o de interés mencionados.
    
    Responde ÚNICAMENTE con un JSON Array (una lista de objetos).
    Ejemplo: [ {"placeName": "A", ...}, {"placeName": "B", ...} ]
    
    INSTRUCCIONES:
    1. Claves en INGLÉS. Valores en ESPAÑOL.
    2. Si hay varios lugares, crea un objeto para cada uno.
    
    Plantilla de Objeto:
    {
      "category": "Lugar/Comida/Otro",
      "placeName": "Nombre específico",
      "estimatedLocation": "Ciudad, País",
      "priceRange": "Precio estimado",
      "summary": "Resumen específico de ESTE lugar en español",
      "score": 5,
      "confidenceLevel": "Alto",
      "criticalVerdict": "Opinión crítica",
      "isTouristTrap": false
    }
    """
    
    response = model.generate_content([video_file, prompt], generation_config={"response_mime_type": "application/json"})
    
    try: genai.delete_file(video_file.name)
    except: pass

    # Parseo Inteligente (Maneja Listas)
    clean_text = response.text.replace("```json", "").replace("```", "").strip()
    try:
        raw_data = json.loads(clean_text)
    except:
        raw_data = []

    # Si Gemini devuelve un solo objeto por error, lo convertimos en lista
    if isinstance(raw_data, dict): raw_data = [raw_data]
    
    final_results = []
    
    # PROCESAMOS CADA LUGAR ENCONTRADO
    for item in raw_data:
        guessed_name = str(item.get("placeName") or "Desconocido")
        guessed_loc = str(item.get("estimatedLocation") or "")
        
        # Verificación individual en Maps
        maps_data = verify_location_with_maps(guessed_name, guessed_loc)
        
        final_name = maps_data["officialName"] if maps_data else guessed_name
        final_loc = maps_data["address"] if maps_data else guessed_loc

        safe_record = {
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "category": str(item.get("category") or "Otro"),
            "placeName": final_name,
            "estimatedLocation": final_loc,
            "priceRange": str(item.get("priceRange") or "??"),
            "summary": str(item.get("summary") or "Sin resumen"),
            "score": item.get("score") or 0,
            "confidenceLevel": str(item.get("confidenceLevel") or "Bajo"),
            "criticalVerdict": str(item.get("criticalVerdict") or ""),
            "isTouristTrap": bool(item.get("isTouristTrap")),
            "fileName": "Video TikTok"
        }
        final_results.append(safe_record)

    return final_results # Devuelve una LISTA

# --- RUTAS ---
@app.route('/analyze', methods=['POST'])
def analyze_video():
    try:
        data = request.json
        if isinstance(data, list): data = data[0]
        url = data.get('url')
        if not url: return jsonify({"error": "No URL"}), 400

        video_path = download_video(url)
        if not video_path: return jsonify({"error": "Error descarga"}), 500

        # Obtenemos la LISTA de resultados
        results_list = analyze_with_gemini(video_path)
        
        # Devolvemos la lista completa al frontend
        # NOTA: El frontend debe estar listo para recibir un Array
        return jsonify(results_list)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        try:
            if 'video_path' in locals() and video_path and os.path.exists(video_path):
                os.remove(video_path)
        except: pass

@app.route('/api/history', methods=['GET'])
def get_history():
    sheet = get_db_connection()
    try: raw = sheet.get_all_records() if sheet else LOCAL_DB
    except: raw = LOCAL_DB
    
    # Limpieza básica
    clean = []
    for r in raw:
        if isinstance(r, dict): clean.append(r)
    return jsonify(clean)

@app.route('/api/history', methods=['POST'])
def save_history():
    # Esta ruta ahora debe ser inteligente.
    # El frontend puede mandar UN objeto o UNA LISTA de objetos.
    data = request.json
    sheet = get_db_connection()
    
    items_to_save = []
    if isinstance(data, list):
        items_to_save = data
    else:
        items_to_save = [data] # Convertimos el solitario en lista
        
    saved_count = 0
    if sheet:
        for item in items_to_save:
            try:
                row = [
                    item.get('id'),
                    item.get('timestamp'),
                    item.get('placeName'),
                    item.get('category'),
                    item.get('score'),
                    item.get('estimatedLocation'),
                    item.get('summary'),
                    item.get('fileName')
                ]
                sheet.append_row(row)
                saved_count += 1
            except: pass
    else:
        LOCAL_DB.extend(items_to_save)
        
    return jsonify({"status": "saved", "count": saved_count})

@app.route('/health', methods=['GET'])
def health_check(): return "OK", 200

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

import os
import time
import json
import glob
import tempfile
import uuid
import requests
import gc
import traceback
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import yt_dlp
import google.generativeai as genai
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY") 

print("🚀 INICIANDO: MOTOR GEMINI 2.5 FLASH + GPS IA...", flush=True)

if not API_KEY: print("❌ FATAL: API_KEY no encontrada.", flush=True)
else:
    try: genai.configure(api_key=API_KEY)
    except Exception as e: print(f"❌ Error Gemini Config: {e}", flush=True)

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# --- 1. MODELO (ACTUALIZADO A 2.5) ---
def get_best_model():
    # USAMOS EXPLÍCITAMENTE LA VERSIÓN 2.5 FLASH
    return "gemini-2.5-flash"

# --- 2. FOTOS (UNSPLASH) ---
def get_unsplash_photo(query):
    if not UNSPLASH_KEY: return ""
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://api.unsplash.com/search/photos?page=1&query={safe_query}&per_page=1&orientation=landscape&client_id={UNSPLASH_KEY}"
        res = requests.get(url, timeout=2) 
        if res.status_code == 200:
            data = res.json()
            if "results" in data and len(data["results"]) > 0:
                return data["results"][0]["urls"]["regular"]
    except: pass
    return ""

# --- 3. LÓGICA DE UBICACIÓN (PRIORIDAD IA) ---
def verify_location_hybrid(place_name, location_hint, ai_lat=None, ai_lng=None):
    
    final_lat = ai_lat
    final_lng = ai_lng
    final_address = f"{place_name}, {location_hint}"
    
    # Si la IA falló en darnos coordenadas (0 o None), intentamos OSM con cuidado
    if not final_lat or not final_lng or final_lat == 0:
        print(f"⚠️ IA sin GPS para '{place_name}'. Intentando OSM...", flush=True)
        headers = { 'User-Agent': 'TravelHunterApp/2.0', 'Accept-Language': 'es-ES' }
        try:
            time.sleep(1.0) # Sleep para evitar bloqueo
            q = f"{place_name} {location_hint}"
            res = requests.get("https://nominatim.openstreetmap.org/search", 
                             params={'q': q, 'format': 'json', 'limit': 1}, 
                             headers=headers, timeout=4)
            data = res.json()
            if data:
                final_lat = float(data[0].get('lat'))
                final_lng = float(data[0].get('lon'))
                final_address = data[0].get('display_name')
        except Exception as e:
            print(f"   ❌ Falló OSM también: {e}", flush=True)

    # Foto
    photo_url = get_unsplash_photo(f"{place_name} {location_hint} travel")
    
    # CONSTRUCCIÓN DEL LINK
    if final_lat and final_lng and final_lat != 0:
        maps_link = f"https://www.google.com/maps/search/?api=1&query={final_lat},{final_lng}"
    else:
        safe = urllib.parse.quote(f"{place_name} {location_hint}")
        maps_link = f"https://www.google.com/maps/search/?api=1&query={safe}"

    return {
        "officialName": place_name,
        "address": final_address,
        "lat": final_lat, "lng": final_lng,
        "photoUrl": photo_url,
        "mapsLink": maps_link
    }

# --- 4. PROCESAMIENTO PARALELO ---
def process_single_item(item):
    try:
        guessed_name = str(item.get("placeName") or "Desconocido")
        guessed_loc = str(item.get("estimatedLocation") or "")
        
        try: ai_lat = float(item.get("lat", 0))
        except: ai_lat = 0
        
        try: ai_lng = float(item.get("lng", 0))
        except: ai_lng = 0
        
        geo_data = verify_location_hybrid(guessed_name, guessed_loc, ai_lat, ai_lng)

        return {
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "category": str(item.get("category") or "Otro"),
            "placeName": geo_data["officialName"],
            "estimatedLocation": geo_data["address"],
            "priceRange": str(item.get("priceRange") or "??"),
            "summary": str(item.get("summary") or ""),
            "score": item.get("score") or 0,
            "isTouristTrap": bool(item.get("isTouristTrap")),
            "fileName": "Video TikTok",
            "photoUrl": geo_data["photoUrl"],
            "mapsLink": geo_data["mapsLink"],
            "confidenceLevel": "Alto", "criticalVerdict": "", "realRating": 0, "website": "", "openNow": ""
        }
    except Exception as e:
        print(f"⚠️ Error item: {e}")
        return None

# --- 5. ANÁLISIS ---
def download_video(url):
    print(f"⬇️ Descargando: {url}", flush=True)
    temp_dir = tempfile.mkdtemp()
    tmpl = os.path.join(temp_dir, f'video_{int(time.time())}.%(ext)s')
    opts = { 'format': 'worst[ext=mp4]', 'outtmpl': tmpl, 'quiet': True, 'no_warnings': True, 'nocheckcertificate': True }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([url])
        files = glob.glob(os.path.join(temp_dir, 'video_*'))
        gc.collect()
        return files[0] if files else None
    except: return None

def analyze_with_gemini(video_path):
    print(f"📤 Subiendo...", flush=True)
    video_file = genai.upload_file(path=video_path)
    
    while video_file.state.name == "PROCESSING":
        time.sleep(1)
        video_file = genai.get_file(video_file.name)
        
    # USAMOS MODELO 2.5 FLASH
    model = genai.GenerativeModel(model_name="gemini-2.5-flash")

    # PROMPT
    prompt = """
    Analiza este video de viaje. Identifica TODOS los lugares turísticos.
    
    REGLAS OBLIGATORIAS:
    1. IDIOMA: Español Latino.
    2. GPS: Estima latitud (lat) y longitud (lng) para CADA lugar.
    
    OUTPUT: JSON Array.
    Estructura PLANA:
    {
      "category": "...", 
      "placeName": "Nombre", 
      "estimatedLocation": "Ciudad", 
      "lat": -13.1631, 
      "lng": -72.5450, 
      "priceRange": "...", 
      "summary": "...", 
      "score": 4.5, 
      "isTouristTrap": false
    }
    """
    
    try:
        response = model.generate_content([video_file, prompt], generation_config={"response_mime_type": "application/json"})
        clean = response.text.replace("```json", "").replace("```", "").strip()
        raw_data = json.loads(clean)
    except Exception as e:
        print(f"❌ Error IA: {e}", flush=True)
        raw_data = []
    
    try: genai.delete_file(video_file.name)
    except: pass

    if isinstance(raw_data, dict): raw_data = [raw_data]
    
    print(f"⚡ Procesando {len(raw_data)} lugares...", flush=True)
    
    final_results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_single_item, raw_data))
        final_results = [r for r in results if r is not None]

    return final_results

# --- RUTAS ---
@app.route('/analyze', methods=['POST'])
def analyze_video_route():
    try:
        data = request.json
        url = data.get('url') if isinstance(data, dict) else data[0].get('url')
        video_path = download_video(url)
        if not video_path: return jsonify({"error": "Error descarga"}), 500
        results = analyze_with_gemini(video_path)
        return jsonify(results) 
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally: gc.collect()

def get_db_connection():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not creds_json or not sheet_id: return None
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), ['https://www.googleapis.com/auth/spreadsheets'])
        return gspread.authorize(creds).open_by_key(sheet_id).sheet1
    except: return None

@app.route('/api/history', methods=['POST', 'GET'])
def handle_history():
    sheet = get_db_connection()
    if request.method == 'GET':
        if not sheet: return jsonify([])
        try:
            raw = sheet.get_all_records()
            clean = []
            for row in raw:
                r = {k.lower().strip(): v for k, v in row.items()}
                clean.append({
                    "id": str(r.get('id') or uuid.uuid4()),
                    "placeName": str(r.get('placename') or r.get('place name') or "Lugar"),
                    "estimatedLocation": str(r.get('estimatedlocation') or ""),
                    "category": str(r.get('category') or "General"),
                    "score": r.get('score') or 0,
                    "summary": str(r.get('summary') or ""),
                    "photoUrl": str(r.get('photourl') or r.get('photo url') or ""),
                    "mapsLink": str(r.get('mapslink') or r.get('maps link') or ""),
                    "isTouristTrap": str(r.get('istouristtrap')).lower() == 'true',
                    "priceRange": str(r.get('pricerange') or "??")
                })
            return jsonify(clean)
        except: return jsonify([])

    try: 
        new_items = request.json
        if not isinstance(new_items, list): new_items = [new_items]
        if not sheet: return jsonify({"status": "local"})
        existing = sheet.get_all_records()
        name_map = {str(r.get('placeName', '')).strip().lower(): i+2 for i, r in enumerate(existing)}
        rows = []
        for item in new_items:
            key = str(item.get('placeName', '')).strip().lower()
            if key not in name_map:
                rows.append([
                    item.get('id'), item.get('timestamp'), item.get('placeName'), item.get('category'), 
                    item.get('score'), item.get('estimatedLocation'), item.get('summary'), 
                    item.get('fileName'), item.get('photoUrl'), item.get('mapsLink'), "", 0
                ])
        if rows: sheet.append_rows(rows)
        return jsonify({"status": "saved"})
    except: return jsonify({"error": "save"}), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

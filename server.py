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

# --- CONFIGURACIÓN ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY") 

print("🚀 INICIANDO MODO NEXT-GEN (GEMINI 2.5 + OPEN SOURCE)...", flush=True)

if not API_KEY: 
    print("❌ FATAL: API_KEY no encontrada.", flush=True)
else:
    try: 
        genai.configure(api_key=API_KEY)
        print("✅ Cliente Gemini configurado.", flush=True)
    except Exception as e: 
        print(f"❌ Error Gemini Config: {e}", flush=True)

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# --- 1. SELECCIÓN DE MODELO (PRIORIDAD: 2.5 FLASH) ---
def get_best_model():
    """Busca el mejor modelo disponible en tu cuenta (Prioridad: Flash 2.5)."""
    print("🔍 Escaneando modelos disponibles...", flush=True)
    
    # 1. Lista de deseos (Orden de preferencia según tu captura)
    wishlist = [
        "gemini-2.5-flash",          # Tu favorito (Gratis/Rápido)
        "gemini-2.5-flash-preview",  # Variante común
        "gemini-2.5-flash-001",      # Variante técnica
        "gemini-3-flash-preview",    # Siguiente generación
        "gemini-2.0-flash-exp",      # Anterior experimental
        "gemini-1.5-flash"           # Fallback clásico
    ]

    try:
        # Obtenemos la lista REAL de modelos que ve tu API Key
        available_models = [m.name for m in genai.list_models()]
        print(f"📋 Modelos reales detectados en tu cuenta: {available_models}", flush=True)

        # Buscamos coincidencia
        for target in wishlist:
            # Buscamos si el nombre deseado está contenido en alguno de los disponibles
            # (Ej: 'models/gemini-2.5-flash' contiene 'gemini-2.5-flash')
            for real_model in available_models:
                if target in real_model:
                    print(f"✅ MATCH: Usando modelo {real_model}", flush=True)
                    return real_model
        
        # Si ninguno de la lista está, usamos el PRIMERO que sirva para generar texto
        print("⚠️ No se encontró modelo específico. Usando el primero disponible...", flush=True)
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                return m.name

    except Exception as e:
        print(f"❌ Error listando modelos: {e}", flush=True)
    
    # Fallback desesperado (A veces funciona aunque no salga en la lista)
    return "gemini-2.5-flash"

# --- 2. FOTOS GRATIS (UNSPLASH) ---
def get_unsplash_photo(query):
    if not UNSPLASH_KEY: return ""
    try:
        safe_query = urllib.parse.quote(query)
        url = f"https://api.unsplash.com/search/photos?page=1&query={safe_query}&per_page=1&orientation=landscape&client_id={UNSPLASH_KEY}"
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if "results" in data and len(data["results"]) > 0:
                return data["results"][0]["urls"]["regular"]
    except: pass
    return ""

# --- 3. MAPAS GRATIS (NOMINATIM / OSM) ---
def verify_location_opensource(place_name, location_hint):
    search_query = f"{place_name} {location_hint}"
    url = "https://nominatim.openstreetmap.org/search"
    headers = { 'User-Agent': 'TravelHunterApp/2.0' }
    params = { 'q': search_query, 'format': 'json', 'limit': 1 }
    
    try:
        print(f"🌍 Buscando en OSM: {search_query}...", flush=True)
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        
        if data and len(data) > 0:
            best = data[0]
            lat, lon = best.get('lat'), best.get('lon')
            maps_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
            # Foto temática
            photo_keyword = f"{place_name} travel"
            photo_url = get_unsplash_photo(photo_keyword)

            return {
                "officialName": place_name, 
                "address": best.get('display_name', location_hint),
                "placeId": str(best.get('place_id', 'osm')),
                "lat": lat, "lng": lon,
                "photoUrl": photo_url,
                "rating": 0, "reviews": 0, "website": "", 
                "mapsLink": maps_link, "openNow": "", "phone": ""
            }
    except Exception as e: print(f"⚠️ Error OSM: {e}", flush=True)
    
    # Fallback solo foto
    photo_url = get_unsplash_photo(f"{place_name} {location_hint}")
    if photo_url:
         return {
            "officialName": place_name, "address": location_hint,
            "placeId": "manual", "lat": "", "lng": "",
            "photoUrl": photo_url, "rating": 0, "reviews": 0, "website": "", 
            "mapsLink": "", "openNow": "", "phone": ""
        }
    return None

# --- 4. VIDEO ---
def download_video(url):
    print(f"⬇️ Descargando: {url}", flush=True)
    temp_dir = tempfile.mkdtemp()
    output_template = os.path.join(temp_dir, f'video_{int(time.time())}.%(ext)s')
    ydl_opts = { 'format': 'worst[ext=mp4]', 'outtmpl': output_template, 'quiet': True, 'no_warnings': True, 'nocheckcertificate': True }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        files = glob.glob(os.path.join(temp_dir, 'video_*'))
        gc.collect()
        return files[0] if files else None
    except Exception as e:
        print(f"❌ Error descarga: {e}", flush=True)
        return None

# --- 5. ANÁLISIS ---
def analyze_with_gemini(video_path):
    print(f"📤 Subiendo video...", flush=True)
    video_file = None
    try:
        video_file = genai.upload_file(path=video_path)
        while video_file.state.name == "PROCESSING":
            time.sleep(1)
            video_file = genai.get_file(video_file.name)
        if video_file.state.name == "FAILED": raise Exception("Video rechazado")
    except: raise Exception("Error subiendo video")

    # AQUÍ ES DONDE ELEGIMOS TU MODELO 2.5
    active_model = get_best_model()
    print(f"🤖 INICIANDO ANÁLISIS CON: {active_model}", flush=True)
    
    try:
        model = genai.GenerativeModel(model_name=active_model)
    except: raise Exception(f"No se pudo cargar {active_model}")

    prompt = """
    Analiza este video de viaje. Identifica TODOS los lugares turísticos.
    OUTPUT: JSON Array ONLY. NO Markdown.
    LANGUAGE: SPANISH.
    Structure: {"category": "...", "placeName": "...", "estimatedLocation": "...", "priceRange": "...", "summary": "...", "score": 4.5, "confidenceLevel": "...", "criticalVerdict": "...", "isTouristTrap": boolean}
    """
    
    try:
        response = model.generate_content([video_file, prompt], generation_config={"response_mime_type": "application/json"})
        clean = response.text.replace("```json", "").replace("```", "").strip()
        raw_data = json.loads(clean)
    except Exception as e:
        print(f"❌ Error Generación IA: {e}", flush=True)
        raw_data = []
    
    try: 
        if video_file: genai.delete_file(video_file.name)
    except: pass
    gc.collect() 

    if isinstance(raw_data, dict): raw_data = [raw_data]
    final_results = []
    
    for item in raw_data:
        guessed_name = str(item.get("placeName") or "Desconocido")
        guessed_loc = str(item.get("estimatedLocation") or "")
        
        # MODO OPEN SOURCE
        opensource_data = verify_location_opensource(guessed_name, guessed_loc)
        
        if opensource_data:
            final_name = opensource_data["officialName"]
            final_loc = opensource_data["address"]
            photo_url = opensource_data["photoUrl"]
            maps_link = opensource_data["mapsLink"]
        else:
            final_name = guessed_name
            final_loc = guessed_loc
            photo_url = ""
            maps_link = ""

        final_results.append({
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "category": str(item.get("category") or "Otro"),
            "placeName": final_name,
            "estimatedLocation": final_loc,
            "priceRange": str(item.get("priceRange") or "??"),
            "summary": str(item.get("summary") or ""),
            "score": item.get("score") or 0,
            "confidenceLevel": str(item.get("confidenceLevel") or "Bajo"),
            "criticalVerdict": str(item.get("criticalVerdict") or ""),
            "isTouristTrap": bool(item.get("isTouristTrap")),
            "fileName": "Video TikTok",
            "photoUrl": photo_url,
            "realRating": 0, "realReviews": 0, "website": "", 
            "mapsLink": maps_link, "openNow": "", "phone": ""
        })

    return final_results

# --- RUTAS ---
@app.route('/analyze', methods=['POST'])
def analyze_video_route():
    try:
        data = request.json
        if isinstance(data, list): data = data[0]
        url = data.get('url')
        if not url: return jsonify({"error": "No URL"}), 400
        video_path = download_video(url)
        if not video_path: return jsonify({"error": "Error descarga"}), 500
        results = analyze_with_gemini(video_path)
        return jsonify(results) 
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally: gc.collect()

# --- DB ---
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
    except: return None

@app.route('/api/history', methods=['POST', 'GET'])
def handle_history():
    sheet = get_db_connection()
    if request.method == 'GET':
        try: raw = sheet.get_all_records() if sheet else []
        except: raw = []
        return jsonify([r for r in raw if isinstance(r, dict)])
    
    # POST
    try:
        new_items = request.json
        if not isinstance(new_items, list): new_items = [new_items]
        if not sheet: return jsonify({"status": "local"})

        try: existing = sheet.get_all_records()
        except: existing = []
        name_map = {str(r.get('placeName', '')).strip().lower(): i+2 for i, r in enumerate(existing)}
        rows = []

        for item in new_items:
            name = str(item.get('placeName', '')).strip()
            key = name.lower()
            photo = item.get('photoUrl') or ""
            if key in name_map:
                try:
                    idx = name_map[key]
                    sheet.update_cell(idx, 5, item.get('score'))
                    if photo: sheet.update_cell(idx, 9, photo)
                except: pass
            else:
                rows.append([
                    item.get('id'), item.get('timestamp'), name, item.get('category'), 
                    item.get('score'), item.get('estimatedLocation'), item.get('summary'), 
                    item.get('fileName'), photo, item.get('mapsLink'), "", 0
                ])
        if rows: sheet.append_rows(rows)
        return jsonify({"status": "saved"})
    except: return jsonify({"error": "save error"}), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

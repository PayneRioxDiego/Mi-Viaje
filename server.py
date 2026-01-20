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
from concurrent.futures import ThreadPoolExecutor # <--- EL SECRETO DE LA VELOCIDAD

# --- CONFIGURACIÓN ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY") 

print("🚀 INICIANDO MODO TURBO (PARALELO + ESPAÑOL)...", flush=True)

if not API_KEY: 
    print("❌ FATAL: API_KEY no encontrada.", flush=True)
else:
    try: 
        genai.configure(api_key=API_KEY)
    except Exception as e: 
        print(f"❌ Error Gemini Config: {e}", flush=True)

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# --- 1. MODELO ---
def get_best_model():
    wishlist = ["gemini-2.5-flash", "gemini-2.5-flash-latest", "gemini-1.5-flash"]
    try:
        available = [m.name for m in genai.list_models()]
        for target in wishlist:
            for real in available:
                if target in real: return real
        return "gemini-1.5-flash"
    except: return "gemini-1.5-flash"

# --- 2. FOTOS (UNSPLASH) - CON TIMEOUT CORTO ---
def get_unsplash_photo(query):
    if not UNSPLASH_KEY: return ""
    try:
        safe_query = urllib.parse.quote(query)
        # Timeout agresivo de 2s para no colgar el servidor
        url = f"https://api.unsplash.com/search/photos?page=1&query={safe_query}&per_page=1&orientation=landscape&client_id={UNSPLASH_KEY}"
        res = requests.get(url, timeout=2) 
        if res.status_code == 200:
            data = res.json()
            if "results" in data and len(data["results"]) > 0:
                return data["results"][0]["urls"]["regular"]
    except: pass
    return ""

# --- 3. MAPAS HÍBRIDOS (OSM + IA) - OPTIMIZADO EN ESPAÑOL ---
def verify_location_hybrid(place_name, location_hint, ai_lat=None, ai_lng=None):
    # HEADER CORREGIDO: Forzamos idioma Español para los resultados de mapas
    headers = { 
        'User-Agent': 'TravelHunterApp/Turbo',
        'Accept-Language': 'es-ES,es;q=0.9' 
    }
    
    clean_name = place_name
    for word in ["tour", "full day", "trekking", "caminata", "visita", "excursion", "viaje a"]:
        clean_name = clean_name.lower().replace(word, "").strip()
    
    best_result = None

    # Intentamos OSM solo si vale la pena (timeout corto)
    queries = [f"{clean_name} {location_hint}", clean_name]
    
    for query in queries:
        try:
            if len(query) < 3: continue
            # Timeout de 3s máximo por intento
            response = requests.get("https://nominatim.openstreetmap.org/search", 
                                  params={'q': query, 'format': 'json', 'limit': 1}, 
                                  headers=headers, timeout=3)
            data = response.json()
            if data:
                best_result = data[0]
                break
        except: pass

    final_lat = ""
    final_lng = ""
    
    if best_result:
        final_lat = best_result.get('lat')
        final_lng = best_result.get('lon')
        final_address = best_result.get('display_name')
    elif ai_lat and ai_lng and ai_lat != 0:
        final_lat = ai_lat
        final_lng = ai_lng
        final_address = f"{place_name}, {location_hint}"
    else:
        final_address = location_hint

    # Foto en paralelo (dentro del hilo)
    photo_url = get_unsplash_photo(f"{clean_name} {location_hint} travel")
    
    # GENERACIÓN DE LINK CORREGIDA: Solo generamos link si hay coordenadas reales
    if final_lat and final_lng:
        maps_link = f"https://www.google.com/maps/search/?api=1&query={final_lat},{final_lng}"
    else:
        search_safe = urllib.parse.quote(f"{place_name} {location_hint}")
        maps_link = f"https://www.google.com/maps/search/?api=1&query={search_safe}"

    return {
        "officialName": place_name,
        "address": final_address,
        "lat": final_lat, "lng": final_lng,
        "photoUrl": photo_url,
        "mapsLink": maps_link
    }

# --- 4. PROCESAMIENTO PARALELO ---
def process_single_item(item):
    """Procesa UN solo item (Mapa + Foto). Esta función correrá en paralelo."""
    try:
        guessed_name = str(item.get("placeName") or "Desconocido")
        guessed_loc = str(item.get("estimatedLocation") or "")
        
        # GPS de la IA
        ai_gps = item.get("gps") or {}
        ai_lat = ai_gps.get("lat", 0)
        ai_lng = ai_gps.get("lng", 0)
        
        # Verificación pesada (OSM + Unsplash)
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
            "confidenceLevel": "Alto", "criticalVerdict": "", "realRating": 0, "website": "", "openNow": "", "phone": ""
        }
    except Exception as e:
        print(f"⚠️ Error procesando item individual: {e}")
        return None

# --- 5. VIDEO & ANÁLISIS ---
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
    except: return None

def analyze_with_gemini(video_path):
    print(f"📤 Subiendo video a Gemini...", flush=True)
    video_file = genai.upload_file(path=video_path)
    
    # Espera activa con log
    dots = 0
    while video_file.state.name == "PROCESSING":
        time.sleep(1)
        dots += 1
        if dots % 5 == 0: print(f"   ⏳ Procesando en Google... ({dots}s)", flush=True)
        video_file = genai.get_file(video_file.name)
        
    if video_file.state.name == "FAILED": raise Exception("Google rechazó el video")

    active_model = get_best_model()
    print(f"🤖 Analizando con {active_model}...", flush=True)
    model = genai.GenerativeModel(model_name=active_model)

    # PROMPT CORREGIDO: Estricto con el idioma y las coordenadas
    prompt = """
    Eres un experto guía de viajes local. Analiza este video.
    Identifica TODOS los lugares turísticos mostrados.
    
    REGLAS OBLIGATORIAS:
    1. IDIOMA: TODA la respuesta (nombres, resumen, categorias) DEBE ser en ESPAÑOL LATINO.
    2. COORDENADAS: Estima latitud y longitud (gps) para CADA lugar. Si no es exacto, estima la ciudad. NUNCA lo dejes vacio.
    
    OUTPUT: JSON Array ONLY. 
    Structure:
    {
      "category": "Comida/Alojamiento/Actividad/Paisaje",
      "placeName": "Nombre en Español",
      "estimatedLocation": "Ciudad, País (en Español)",
      "gps": { "lat": -0.0000, "lng": -0.0000 }, 
      "priceRange": "Gratis/Barato/Moderado/Caro",
      "summary": "Resumen atractivo y útil en español (máx 20 palabras)",
      "score": 4.5,
      "isTouristTrap": boolean
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
    
    print(f"⚡ Iniciando procesamiento paralelo de {len(raw_data)} lugares found...", flush=True)
    
    # --- AQUÍ OCURRE LA MAGIA PARALELA ---
    final_results = []
    # Usamos 5 "trabajadores" simultáneos
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Mapeamos la función a los datos
        results = list(executor.map(process_single_item, raw_data))
        # Filtramos los nulos (errores)
        final_results = [r for r in results if r is not None]

    print(f"✅ Procesamiento terminado. Retornando {len(final_results)} resultados.", flush=True)
    return final_results

# --- RUTAS Y DB ---
@app.route('/analyze', methods=['POST'])
def analyze_video_route():
    try:
        data = request.json
        if isinstance(data, list): data = data[0]
        url = data.get('url')
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
        creds_dict = json.loads(creds_json)
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPES)
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
                    "estimatedLocation": str(r.get('estimatedlocation') or r.get('estimated location') or ""),
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
    except: return jsonify({"error": "save"}), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

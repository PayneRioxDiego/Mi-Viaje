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
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY") # Nueva clave para fotos gratis

print("🚀 INICIANDO MODO OPEN SOURCE (SIN TARJETA)...", flush=True)

if not API_KEY: 
    print("❌ FATAL: API_KEY (Gemini) no encontrada.", flush=True)
else:
    try: 
        genai.configure(api_key=API_KEY)
        print("✅ Gemini Configurado.", flush=True)
    except Exception as e: 
        print(f"❌ Error Gemini Config: {e}", flush=True)

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# --- 1. SELECCIÓN DE MODELO GRATIS (AI STUDIO) ---
def get_free_model():
    candidates = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-flash-001"]
    for m in candidates:
        try:
            model = genai.GenerativeModel(model_name=m)
            model.count_tokens("test")
            return m
        except: continue
    return "gemini-pro"

# --- 2. SISTEMA DE FOTOS GRATIS (UNSPLASH) ---
def get_unsplash_photo(query):
    if not UNSPLASH_KEY: return ""
    try:
        # Buscamos una foto vertical (portrait) o paisaje relacionada con el lugar
        url = f"https://api.unsplash.com/search/photos?page=1&query={urllib.parse.quote(query)}&per_page=1&orientation=landscape&client_id={UNSPLASH_KEY}"
        res = requests.get(url, timeout=3)
        data = res.json()
        if "results" in data and len(data["results"]) > 0:
            return data["results"][0]["urls"]["regular"]
    except: pass
    return ""

# --- 3. SISTEMA DE MAPAS GRATIS (OPENSTREETMAP) ---
def verify_location_opensource(place_name, location_hint):
    # Nominatim es gratis y no requiere Key, pero pide un User-Agent
    search_query = f"{place_name} {location_hint}"
    url = "https://nominatim.openstreetmap.org/search"
    
    headers = {
        'User-Agent': 'TravelHunterApp/1.0' # Requisito de cortesía de OSM
    }
    params = {
        'q': search_query,
        'format': 'json',
        'limit': 1,
        'addressdetails': 1
    }
    
    try:
        print(f"🌍 Buscando en OpenStreetMap: {search_query}...", flush=True)
        response = requests.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        
        if data and len(data) > 0:
            best = data[0]
            display_name = best.get('display_name', '')
            lat = best.get('lat')
            lon = best.get('lon')
            
            # Generamos link de mapa abierto
            maps_link = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=16/{lat}/{lon}"
            # O link de Google Maps (funciona sin API key, solo como link)
            google_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"

            # Conseguimos foto temática de Unsplash
            # Usamos el tipo de lugar o la ciudad para la foto
            photo_keyword = f"{place_name} travel"
            photo_url = get_unsplash_photo(photo_keyword)

            return {
                "officialName": place_name, # OSM a veces da direcciones muy largas, mejor mantener el nombre original
                "address": display_name,
                "placeId": str(best.get('place_id', '')),
                "lat": lat,
                "lng": lon,
                "photoUrl": photo_url,
                "rating": 0, # OSM no tiene ratings
                "reviews": 0,
                "website": "", # Difícil de sacar de OSM
                "mapsLink": google_link, # Usamos link de Google para comodidad del usuario
                "openNow": "",
                "phone": ""
            }
    except Exception as e:
        print(f"⚠️ Error OSM: {e}", flush=True)
    
    # Si OSM falla, intentamos al menos conseguir una foto con el nombre
    photo_url = get_unsplash_photo(f"{place_name} {location_hint}")
    if photo_url:
         return {
            "officialName": place_name,
            "address": location_hint,
            "placeId": "manual",
            "lat": "", "lng": "",
            "photoUrl": photo_url,
            "rating": 0, "reviews": 0, "website": "", 
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

    active_model = get_free_model()
    print(f"🤖 Analizando con {active_model}...", flush=True)
    
    try:
        model = genai.GenerativeModel(model_name=active_model)
    except:
        raise Exception("Error modelo.")

    prompt = """
    Analiza este video de viaje. Identifica TODOS los lugares turísticos mencionados.
    OUTPUT: JSON Array ONLY. NO Markdown.
    LANGUAGE: SPANISH.
    
    Structure:
    {
      "category": "Comida/Alojamiento/Actividad",
      "placeName": "Nombre",
      "estimatedLocation": "Ciudad, Pais",
      "priceRange": "Gratis/Barato/Moderado/Caro",
      "summary": "Resumen en español",
      "score": 4.5,
      "confidenceLevel": "Alto",
      "criticalVerdict": "Opinion critica",
      "isTouristTrap": boolean
    }
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
        
        # --- AQUÍ USAMOS EL SISTEMA GRATIS ---
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

        combined_summary = str(item.get("summary") or "")

        final_results.append({
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "category": str(item.get("category") or "Otro"),
            "placeName": final_name,
            "estimatedLocation": final_loc,
            "priceRange": str(item.get("priceRange") or "??"),
            "summary": combined_summary,
            "score": item.get("score") or 0,
            "confidenceLevel": str(item.get("confidenceLevel") or "Bajo"),
            "criticalVerdict": str(item.get("criticalVerdict") or ""),
            "isTouristTrap": bool(item.get("isTouristTrap")),
            "fileName": "Video TikTok",
            # Datos Open Source
            "photoUrl": photo_url,
            "realRating": 0, # No hay rating en OSM
            "realReviews": 0,
            "website": "",
            "mapsLink": maps_link,
            "openNow": "",
            "phone": ""
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

# --- GOOGLE SHEETS (Esto es gratis, se mantiene) ---
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

@app.route('/api/history', methods=['POST'])
def save_history():
    try:
        new_items = request.json
        if not isinstance(new_items, list): new_items = [new_items]
        sheet = get_db_connection()
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
                    sheet.update_cell(idx, 7, str(item.get('summary'))[:4500])
                    if photo: sheet.update_cell(idx, 9, photo)
                except: pass
            else:
                rows.append([
                    item.get('id'), item.get('timestamp'), name, item.get('category'), 
                    item.get('score'), item.get('estimatedLocation'), item.get('summary'), 
                    item.get('fileName'), photo, item.get('mapsLink'), 
                    item.get('website'), item.get('realRating')
                ])
        if rows: sheet.append_rows(rows)
        return jsonify({"status": "saved"})
    except: return jsonify({"error": "save error"}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    sheet = get_db_connection()
    try: raw = sheet.get_all_records() if sheet else []
    except: raw = []
    return jsonify([r for r in raw if isinstance(r, dict)])

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

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

# --- CONFIGURACIÓN ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

print("🚀 INICIANDO SERVIDOR (MODO AUTO-DESCUBRIMIENTO)...", flush=True)

if not API_KEY: 
    print("❌ FATAL: API_KEY no encontrada.", flush=True)
else:
    try: 
        genai.configure(api_key=API_KEY)
        print("✅ Cliente Gemini inicializado.", flush=True)
    except Exception as e: 
        print(f"❌ Error Gemini Config: {e}", flush=True)

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# --- MAGIA: BUSCADOR DE MODELOS REALES ---
def find_working_model():
    """Pregunta a la API qué modelos sirven con ESTA clave."""
    print("🔍 Escaneando modelos compatibles con tu clave...", flush=True)
    try:
        # Obtenemos la lista real que Google nos permite usar
        models = list(genai.list_models())
        viable_models = []
        
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                viable_models.append(m.name)
        
        print(f"📋 Modelos encontrados: {viable_models}", flush=True)
        
        # Filtramos por preferencia (Gratis > Pro)
        # Buscamos cualquiera que tenga 'flash' (suele ser el gratis/rápido)
        for m in viable_models:
            if 'flash' in m.lower() and '1.5' in m:
                print(f"🎯 Seleccionado Preferido: {m}", flush=True)
                return m
                
        # Si no hay flash 1.5, probamos el 2.0 (experimental)
        for m in viable_models:
            if 'flash' in m.lower() and '2.0' in m:
                print(f"🎯 Seleccionado Experimental: {m}", flush=True)
                return m

        # Si no, el primero que funcione
        if viable_models:
            print(f"⚠️ Usando fallback: {viable_models[0]}", flush=True)
            return viable_models[0]
            
    except Exception as e:
        print(f"❌ Error listando modelos: {e}", flush=True)
        print("⚠️ Intentando forzar 'gemini-1.5-flash' a ciegas...", flush=True)
        return "gemini-1.5-flash"
    
    return "gemini-pro" # Último recurso

# Guardamos el modelo elegido en una variable global
ACTIVE_MODEL_NAME = "gemini-1.5-flash" # Valor inicial por defecto

# Ejecutamos la búsqueda AL ARRANCAR para ver el log inmediato
try:
    ACTIVE_MODEL_NAME = find_working_model()
except: pass

# --- 1. GOOGLE SHEETS ---
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

# --- 2. MAPS (MODO SEGURO - SIN COBRO) ---
def verify_location_with_maps(place_name, location_hint):
    if not MAPS_API_KEY: return None
    
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.id,places.location,places.photos,places.rating,places.userRatingCount,places.websiteUri,places.googleMapsUri,places.regularOpeningHours"
    }
    query = f"{place_name} {location_hint}"
    payload = {"textQuery": query}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        # Si falla (403 Facturación), lo ignoramos silenciosamente
        if response.status_code != 200: return None

        data = response.json()
        if "places" in data and len(data["places"]) > 0:
            best = data["places"][0]
            
            photo_url = ""
            if "photos" in best and len(best["photos"]) > 0:
                photo_ref = best["photos"][0]["name"]
                photo_url = f"https://places.googleapis.com/v1/{photo_ref}/media?maxHeightPx=600&maxWidthPx=600&key={MAPS_API_KEY}"

            open_now = ""
            try:
                is_open = best.get("regularOpeningHours", {}).get("openNow")
                if is_open is True: open_now = "Abierto"
                elif is_open is False: open_now = "Cerrado"
            except: pass

            return {
                "officialName": best.get("displayName", {}).get("text"),
                "address": best.get("formattedAddress"),
                "placeId": best.get("id"),
                "lat": best.get("location", {}).get("latitude"),
                "lng": best.get("location", {}).get("longitude"),
                "photoUrl": photo_url,
                "rating": best.get("rating", 0),
                "reviews": best.get("userRatingCount", 0),
                "website": best.get("websiteUri", ""),
                "mapsLink": best.get("googleMapsUri", ""),
                "openNow": open_now,
                "phone": ""
            }
    except: return None

# --- 3. VIDEO ---
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

# --- 4. ANÁLISIS ---
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

    print(f"🤖 Analizando con modelo activo: {ACTIVE_MODEL_NAME}...", flush=True)
    
    try:
        model = genai.GenerativeModel(model_name=ACTIVE_MODEL_NAME)
    except:
        raise Exception(f"No se pudo cargar el modelo {ACTIVE_MODEL_NAME}")

    prompt = """
    Analiza este video de viaje. Identifica TODOS los lugares turísticos.
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
        
        maps = verify_location_with_maps(guessed_name, guessed_loc)
        
        final_name = maps["officialName"] if maps else guessed_name
        final_loc = maps["address"] if maps else guessed_loc
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
            "photoUrl": maps["photoUrl"] if maps else "",
            "realRating": maps["rating"] if maps else 0,
            "realReviews": maps["reviews"] if maps else 0,
            "website": maps["website"] if maps else "",
            "mapsLink": maps["mapsLink"] if maps else "",
            "openNow": maps["openNow"] if maps else "",
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

# --- SHEET CONNECTION ---
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

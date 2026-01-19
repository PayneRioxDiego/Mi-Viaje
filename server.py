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

print("🚀 INICIANDO SERVIDOR (NEXT-GEN MODELS)...", flush=True)

if not API_KEY: 
    print("❌ FATAL: API_KEY no encontrada.", flush=True)
else:
    try: 
        genai.configure(api_key=API_KEY)
        print("✅ Gemini Configurado.", flush=True)
    except Exception as e: 
        print(f"❌ Error Gemini Config: {e}", flush=True)

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# --- SELECCIÓN DE MODELO INTELIGENTE (Basado en tu captura) ---
def get_best_available_model():
    """Busca específicamente los modelos Gemini 3 y 2.5 que tienes disponibles."""
    print("🔍 Escaneando modelos en tu cuenta...", flush=True)
    try:
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        print(f"📋 Lista completa de modelos: {available_models}", flush=True)

        # PRIORIDAD ABSOLUTA (Según tu imagen)
        target_models = [
            "models/gemini-3-flash-preview", # Lo más top
            "models/gemini-3-pro-preview",
            "models/gemini-2.5-flash",       # Tu preferencia actual
            "models/gemini-2.5-pro",
            "models/gemini-2.0-flash-exp",   # Alias técnico común para 2.5
            "models/gemini-1.5-pro",         # Fallback aceptable
            "models/gemini-1.5-flash"
        ]

        # 1. Búsqueda Exacta
        for target in target_models:
            if target in available_models:
                print(f"🎯 MATCH EXACTO: {target}", flush=True)
                return target

        # 2. Búsqueda Parcial (Si la API usa nombres ligeramente distintos)
        # Busca "gemini-3", luego "gemini-2.5", etc.
        keywords = ["gemini-3", "gemini-2.5", "gemini-2.0", "gemini-1.5"]
        for kw in keywords:
            for av in available_models:
                if kw in av:
                    print(f"🎯 MATCH POR PALABRA CLAVE ({kw}): {av}", flush=True)
                    return av

        # 3. Último recurso: El primero que funcione
        if available_models:
            return available_models[0]
            
    except Exception as e:
        print(f"⚠️ Error listando modelos: {e}", flush=True)
    
    # Fallback ciego si list_models falla (Intentamos pegarle al 2.5 Flash directamente)
    return "gemini-2.5-flash"

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

# --- 2. MAPS + FOTOS ---
def verify_location_with_maps(place_name, location_hint):
    if not MAPS_API_KEY: return None
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.id,places.location,places.photos,places.rating,places.userRatingCount,places.websiteUri,places.internationalPhoneNumber,places.googleMapsUri,places.regularOpeningHours"
    }
    query = f"{place_name} {location_hint}"
    payload = {"textQuery": query}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        data = response.json()
        if "places" in data and len(data["places"]) > 0:
            best = data["places"][0]
            
            # Foto
            photo_url = ""
            if "photos" in best and len(best["photos"]) > 0:
                photo_ref = best["photos"][0]["name"]
                photo_url = f"https://places.googleapis.com/v1/{photo_ref}/media?maxHeightPx=800&maxWidthPx=800&key={MAPS_API_KEY}"
            
            # Horario
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
                "phone": best.get("internationalPhoneNumber", ""),
                "mapsLink": best.get("googleMapsUri", ""),
                "openNow": open_now
            }
    except Exception as e:
        print(f"⚠️ Error Maps: {e}", flush=True)
    return None

# --- 3. VIDEO ---
def download_video(url):
    print(f"⬇️ Descargando: {url}", flush=True)
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
    except Exception as e: 
        raise Exception(f"Error subiendo a Gemini: {e}")

    # --- SELECCIÓN DE MODELO ---
    selected_model_name = get_best_available_model()
    print(f"🤖 Usando Modelo: {selected_model_name}", flush=True)
    
    try:
        model = genai.GenerativeModel(model_name=selected_model_name)
    except Exception as e:
        raise Exception(f"Fallo al iniciar {selected_model_name}: {e}")

    prompt = """
    Analiza este video de viaje. Identifica TODOS los lugares mencionados.
    OUTPUT FORMAT: JSON Array ONLY.
    LANGUAGE: All text values MUST be in SPANISH.
    
    Required JSON Structure per item:
    {
      "category": "Comida / Alojamiento / Actividad",
      "placeName": "Name of the place",
      "estimatedLocation": "City, Country",
      "priceRange": "Gratis / Barato / Moderado / Caro",
      "summary": "Detailed summary in Spanish",
      "score": 4.5,
      "confidenceLevel": "Alto",
      "criticalVerdict": "Critical opinion in Spanish",
      "isTouristTrap": boolean
    }
    """
    
    try:
        response = model.generate_content(
            [video_file, prompt], 
            generation_config={"response_mime_type": "application/json"}
        )
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
            "phone": maps["phone"] if maps else ""
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

@app.route('/api/history', methods=['GET'])
def get_history():
    sheet = get_db_connection()
    try: raw = sheet.get_all_records() if sheet else []
    except: raw = []
    return jsonify([r for r in raw if isinstance(r, dict)])

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

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

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

# --- CONFIGURACIÓN E INICIO ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

print("🚀 INICIANDO SERVIDOR PREMIUM...", flush=True)

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

# --- 1. GOOGLE SHEETS (BASE DE DATOS) ---
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

# --- 2. GOOGLE MAPS (MOTOR DE DATOS VISUALES) ---
def verify_location_with_maps(place_name, location_hint):
    if not MAPS_API_KEY: return None
    
    # Endpoint de Búsqueda de Texto (New Places API)
    url = "https://places.googleapis.com/v1/places:searchText"
    
    # Pedimos TODOS los datos necesarios para el frontend
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
            
            # 1. Procesar FOTO (Pedimos alta resolución para el diseño nuevo)
            photo_url = ""
            if "photos" in best and len(best["photos"]) > 0:
                photo_ref = best["photos"][0]["name"]
                # Max width 800px para que se vea nítida en la tarjeta grande
                photo_url = f"https://places.googleapis.com/v1/{photo_ref}/media?maxHeightPx=800&maxWidthPx=800&key={MAPS_API_KEY}"

            # 2. Procesar Horario
            open_now = ""
            try:
                is_open = best.get("regularOpeningHours", {}).get("openNow", None)
                if is_open is True: open_now = "Abierto Ahora"
                elif is_open is False: open_now = "Cerrado"
            except: pass

            return {
                "officialName": best.get("displayName", {}).get("text"),
                "address": best.get("formattedAddress"),
                "placeId": best.get("id"),
                "lat": best.get("location", {}).get("latitude"),
                "lng": best.get("location", {}).get("longitude"),
                # Datos Ricos
                "photoUrl": photo_url,
                "rating": best.get("rating", 0),
                "reviews": best.get("userRatingCount", 0),
                "website": best.get("websiteUri", ""),
                "phone": best.get("internationalPhoneNumber", ""),
                "mapsLink": best.get("googleMapsUri", ""),
                "openNow": open_now
            }
    except Exception as e:
        print(f"⚠️ Error leve en Maps: {e}", flush=True)
    return None

# --- 3. DETECTIVE DE ESTAFAS (Opcional) ---
def check_reputation_with_google(place_name, location):
    # Saltamos búsqueda web compleja por ahora para priorizar velocidad y estabilidad
    # Si quieres reactivarlo, avísame y lo descomentamos
    return "" 

# --- 4. GESTOR DE VIDEO (YT-DLP) ---
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

# --- 5. CEREBRO IA (GEMINI 1.5) ---
def analyze_with_gemini(video_path):
    print(f"📤 Subiendo video...", flush=True)
    video_file = None
    try:
        video_file = genai.upload_file(path=video_path)
        while video_file.state.name == "PROCESSING":
            time.sleep(1)
            video_file = genai.get_file(video_file.name)
    except Exception as e: 
        raise Exception(f"Error subiendo a Gemini: {e}")

    print("🤖 Analizando...", flush=True)
    
    # LISTA DE MODELOS (Prioridad: Flash -> Pro)
    # Evitamos 'gemini-pro' (v1.0) porque no soporta bien JSON Schema
    models = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-pro"]
    model = None
    
    for m in models:
        try:
            model = genai.GenerativeModel(model_name=m)
            break 
        except: continue
            
    if not model: raise Exception("No se pudo iniciar ningún modelo Gemini 1.5")

    # Prompt estricto para JSON y Español
    prompt = """
    Analiza este video de viaje. Identifica TODOS los lugares, restaurantes o alojamientos mencionados.
    
    OUTPUT FORMAT: JSON Array ONLY. Do not include markdown formatting (```json).
    LANGUAGE: All text values (summary, criticalVerdict, placeName) MUST be in SPANISH.
    
    Required JSON Structure per item:
    {
      "category": "Comida / Alojamiento / Actividad",
      "placeName": "Name of the place",
      "estimatedLocation": "City, Country",
      "priceRange": "Gratis / Barato / Moderado / Caro",
      "summary": "Detailed summary in Spanish",
      "score": 4.5,
      "confidenceLevel": "Alto",
      "criticalVerdict": "Critical opinion in Spanish (e.g. 'Trampa turística')",
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
    
    # Limpieza
    try: 
        if video_file: genai.delete_file(video_file.name)
    except: pass
    gc.collect() 

    if isinstance(raw_data, dict): raw_data = [raw_data]
    final_results = []
    
    # Enriquecimiento con Maps
    for item in raw_data:
        guessed_name = str(item.get("placeName") or "Desconocido")
        guessed_loc = str(item.get("estimatedLocation") or "")
        
        maps = verify_location_with_maps(guessed_name, guessed_loc)
        
        # Prioridad a datos de Maps, fallback a IA
        final_name = maps["officialName"] if maps else guessed_name
        final_loc = maps["address"] if maps else guessed_loc
        
        # Detective Web (Opcional, desactivado por ahora)
        web_verdict = "" 
        
        combined_summary = str(item.get("summary") or "")
        if web_verdict: combined_summary += f"\n\n[🕵️‍♂️ Web]: {web_verdict}"

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
            # DATOS VISUALES (PREMIUM)
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

# --- GUARDADO EN LOTE (MÁXIMO RENDIMIENTO) ---
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
        rows_to_create = []

        for item in new_items:
            name = str(item.get('placeName', '')).strip()
            key = name.lower()
            
            # Datos a guardar
            photo = item.get('photoUrl') or ""
            maps_link = item.get('mapsLink') or ""
            website = item.get('website') or ""
            rating = item.get('realRating') or 0

            if key in name_map:
                try:
                    # Update inteligente: Solo actualiza si falta info o cambió el score
                    row_idx = name_map[key]
                    sheet.update_cell(row_idx, 5, item.get('score')) # Score
                    sheet.update_cell(row_idx, 7, str(item.get('summary'))[:4500]) # Resumen
                    if photo: sheet.update_cell(row_idx, 9, photo) # Col 9: Foto
                except: pass
            else:
                rows_to_create.append([
                    item.get('id'), 
                    item.get('timestamp'), 
                    name,
                    item.get('category'), 
                    item.get('score'), 
                    item.get('estimatedLocation'),
                    item.get('summary'), 
                    item.get('fileName'),
                    photo,       # Col 9
                    maps_link,   # Col 10
                    website,     # Col 11
                    rating       # Col 12
                ])

        if rows_to_create:
            try: sheet.append_rows(rows_to_create)
            except: pass

        return jsonify({"status": "saved", "created": len(rows_to_create)})

    except Exception as e: return jsonify({"error": str(e)}), 500

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

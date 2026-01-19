import os
import time
import json
import glob
import tempfile
import uuid
import requests
import gc
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

# Configuración Gemini
if not API_KEY: print("❌ ERROR: API_KEY not found.")
try: 
    genai.configure(api_key=API_KEY)
    print("✅ Gemini Configurado.")
except Exception as e: 
    print(f"❌ Error Gemini Config: {e}")

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# --- 0. DIAGNÓSTICO AL ARRANQUE (AUTO-DETECCIÓN) ---
ACTIVE_MODEL_NAME = "gemini-pro"

def find_best_model():
    global ACTIVE_MODEL_NAME
    print("🔍 Buscando modelos disponibles en tu cuenta...")
    available_models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        preferred_order = [
            'models/gemini-2.0-flash-exp', 
            'models/gemini-1.5-pro-latest', 
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-flash',
            'models/gemini-pro'
        ]
        
        for pref in preferred_order:
            if pref in available_models:
                ACTIVE_MODEL_NAME = pref
                print(f"🎯 MODELO SELECCIONADO: {ACTIVE_MODEL_NAME}")
                return
        
        if available_models:
            ACTIVE_MODEL_NAME = available_models[0]
            print(f"⚠️ Usando modelo genérico: {ACTIVE_MODEL_NAME}")
            
    except Exception as e:
        print(f"⚠️ Error listando modelos: {e}")

find_best_model()

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
    except Exception as e:
        print(f"❌ Error Sheets: {e}")
        return None

# --- 2. MAPS + FOTOS (NUEVO) ---
def verify_location_with_maps(place_name, location_hint):
    if not MAPS_API_KEY: return None
    url = "https://places.googleapis.com/v1/places:searchText"
    
    # PEDIMOS EL CAMPO 'photos' TAMBIÉN
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.id,places.location,places.photos"
    }
    query = f"{place_name} {location_hint}"
    payload = {"textQuery": query}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        data = response.json()
        if "places" in data and len(data["places"]) > 0:
            best = data["places"][0]
            
            # PROCESAMOS LA FOTO
            photo_url = ""
            if "photos" in best and len(best["photos"]) > 0:
                photo_ref = best["photos"][0]["name"] # formato: places/PLACE_ID/photos/PHOTO_ID
                # Construimos la URL pública de la foto
                photo_url = f"https://places.googleapis.com/v1/{photo_ref}/media?maxHeightPx=400&maxWidthPx=400&key={MAPS_API_KEY}"

            return {
                "officialName": best.get("displayName", {}).get("text"),
                "address": best.get("formattedAddress"),
                "placeId": best.get("id"),
                "lat": best.get("location", {}).get("latitude"),
                "lng": best.get("location", {}).get("longitude"),
                "photoUrl": photo_url # <--- NUEVO CAMPO
            }
    except: pass
    return None

# --- 3. DETECTIVE ---
def check_reputation_with_google(place_name, location):
    print(f"🕵️‍♂️ Investigando: {place_name}...")
    try:
        model = genai.GenerativeModel(ACTIVE_MODEL_NAME)
        prompt = f"""
        Busca en Google: "{place_name}" "{location}" reviews tourist trap scam.
        Analiza los resultados. Responde ÚNICAMENTE en ESPAÑOL.
        Si encuentras advertencias de estafa, descríbelas en 1 frase.
        Si es seguro, responde "OK".
        """
        try:
            response = model.generate_content(prompt, tools='google_search_retrieval')
            verdict = response.text.strip()
            if "OK" in verdict or not verdict: return ""
            return verdict
        except: return "" 
    except: return ""

# --- 4. VIDEO ---
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
        gc.collect()
        return files[0] if files else None
    except: return None

# --- 5. ANÁLISIS ---
def analyze_with_gemini(video_path):
    print(f"📤 Subiendo video...")
    video_file = None
    try:
        video_file = genai.upload_file(path=video_path)
        while video_file.state.name == "PROCESSING":
            time.sleep(1)
            video_file = genai.get_file(video_file.name)
    except Exception as e: raise Exception(f"Error Upload: {e}")

    print(f"🤖 Analizando con: {ACTIVE_MODEL_NAME}")
    try: model = genai.GenerativeModel(model_name=ACTIVE_MODEL_NAME)
    except: model = genai.GenerativeModel(model_name="gemini-pro")

    prompt = """
    Analiza este video. Identifica TODOS los lugares turísticos.
    CRITICAL: All text values MUST be in SPANISH.
    Responde ÚNICAMENTE con JSON Array.
    Plantilla:
    [{
      "category": "Lugar / Comida / Alojamiento",
      "placeName": "Nombre",
      "estimatedLocation": "Ciudad, País",
      "priceRange": "Gratis / Barato / Caro",
      "summary": "Resumen en ESPAÑOL",
      "score": 5,
      "confidenceLevel": "Alto",
      "criticalVerdict": "Opinión en ESPAÑOL",
      "isTouristTrap": false
    }]
    """
    
    try:
        response = model.generate_content([video_file, prompt], generation_config={"response_mime_type": "application/json"})
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        raw_data = json.loads(clean_text)
    except: raw_data = []
    
    try: 
        if video_file: genai.delete_file(video_file.name)
    except: pass
    gc.collect() 

    if isinstance(raw_data, dict): raw_data = [raw_data]
    final_results = []
    
    for item in raw_data:
        guessed_name = str(item.get("placeName") or "Desconocido")
        guessed_loc = str(item.get("estimatedLocation") or "")
        
        maps_data = verify_location_with_maps(guessed_name, guessed_loc)
        
        final_name = maps_data["officialName"] if maps_data else guessed_name
        final_loc = maps_data["address"] if maps_data else guessed_loc
        photo_url = maps_data["photoUrl"] if maps_data else "" # <--- CAPTURAMOS LA FOTO

        web_verdict = ""
        is_trap_confirmed = False
        if final_name != "Desconocido":
            web_verdict = check_reputation_with_google(final_name, final_loc)
            if any(x in web_verdict.lower() for x in ["trampa", "estafa", "scam"]):
                is_trap_confirmed = True

        combined = str(item.get("summary") or "")
        if web_verdict: combined += f"\n\n[🕵️‍♂️ Web]: {web_verdict}"

        final_results.append({
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "category": str(item.get("category") or "Otro"),
            "placeName": final_name,
            "estimatedLocation": final_loc,
            "priceRange": str(item.get("priceRange") or "??"),
            "summary": combined,
            "score": item.get("score") or 0,
            "confidenceLevel": str(item.get("confidenceLevel") or "Bajo"),
            "criticalVerdict": str(item.get("criticalVerdict") or ""),
            "isTouristTrap": is_trap_confirmed or bool(item.get("isTouristTrap")),
            "photoUrl": photo_url, # <--- ENVIAMOS AL FRONTEND
            "fileName": "Video TikTok"
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
        results_list = analyze_with_gemini(video_path)
        return jsonify(results_list) 
    except Exception as e: return jsonify({"error": str(e)}), 500
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
        rows_to_create = []

        for item in new_items:
            name = str(item.get('placeName', '')).strip()
            key = name.lower()
            photo = item.get('photoUrl') or "" # Capturamos foto

            if key in name_map:
                try:
                    row_idx = name_map[key]
                    sheet.update_cell(row_idx, 5, item.get('score'))
                    sheet.update_cell(row_idx, 7, str(item.get('summary'))[:4500])
                    # Si antes no tenía foto y ahora sí, la actualizamos
                    if photo: sheet.update_cell(row_idx, 9, photo) # Asumiendo Col 9 es Foto
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
                    photo # <--- AÑADIMOS LA FOTO AL EXCEL (Nueva Columna)
                ])

        if rows_to_create:
            try: sheet.append_rows(rows_to_create)
            except: pass

        return jsonify({"status": "saved"})

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

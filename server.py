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
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- CONFIGURACIÓN ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# Configuración Gemini
if not API_KEY: print("❌ ERROR: API_KEY not found.")
try: genai.configure(api_key=API_KEY)
except Exception as e: print(f"❌ Error Gemini: {e}")

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)
LOCAL_DB = []

# --- 1. CONEXIÓN A GOOGLE SHEETS ---
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

# --- 2. VERIFICACIÓN CON GOOGLE MAPS ---
def verify_location_with_maps(place_name, location_hint):
    if not MAPS_API_KEY: return None
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": MAPS_API_KEY,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.id,places.location"
    }
    query = f"{place_name} {location_hint}"
    payload = {"textQuery": query}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        data = response.json()
        if "places" in data and len(data["places"]) > 0:
            best = data["places"][0]
            print(f"✅ Maps encontró: {best.get('displayName', {}).get('text')}")
            return {
                "officialName": best.get("displayName", {}).get("text"),
                "address": best.get("formattedAddress"),
                "placeId": best.get("id"),
                "lat": best.get("location", {}).get("latitude"),
                "lng": best.get("location", {}).get("longitude")
            }
    except: pass
    return None

# --- 3. NUEVO: INVESTIGADOR DE REPUTACIÓN (GOOGLE SEARCH) ---
def check_reputation_with_google(place_name, location):
    """Usa Gemini con acceso a Google Search para buscar estafas o validación."""
    print(f"🕵️‍♂️ Investigando reputación de: {place_name}...")
    try:
        # Usamos un modelo ligero capaz de usar herramientas (tools)
        model = genai.GenerativeModel('gemini-1.5-flash') 
        
        prompt = f"""
        Actúa como un detective de viajes escéptico.
        Investiga en Google sobre "{place_name}" en "{location}".
        Busca específicamente: "Tourist trap", "Scam", "Estafa", "Overpriced", "Cerrado permanentemente".
        
        Responde en 1 sola frase en ESPAÑOL con tu veredicto.
        Ejemplo: "Ojo: Muchos blogs reportan que cobran cubiertos extra y la comida es congelada."
        Si todo parece bien, di: "Parece legítimo, tiene buenas menciones recientes."
        """
        
        # Activamos la herramienta de búsqueda
        response = model.generate_content(
            prompt,
            tools='google_search_retrieval' # <--- AQUÍ ESTÁ EL SUPERPODER
        )
        
        verdict = response.text.strip()
        print(f"🕵️‍♂️ Veredicto: {verdict}")
        return verdict
    except Exception as e:
        print(f"⚠️ Error en investigación: {e}")
        return ""

# --- 4. DESCARGA DE VIDEO ---
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

# --- 5. ANÁLISIS PRINCIPAL ---
def analyze_with_gemini(video_path):
    print(f"📤 Subiendo a Gemini...")
    video_file = None
    try:
        video_file = genai.upload_file(path=video_path)
        while video_file.state.name == "PROCESSING":
            time.sleep(1)
            video_file = genai.get_file(video_file.name)
    except Exception as e: raise Exception(f"Error Gemini Upload: {e}")

    print("🤖 Analizando Video...")
    try: model = genai.GenerativeModel(model_name="gemini-2.5-flash") # O 1.5 Pro
    except: model = genai.GenerativeModel(model_name="gemini-1.5-pro")
    
    prompt = """
    Analiza este video. Identifica TODOS los lugares turísticos.
    Responde ÚNICAMENTE con JSON Array. Ejemplo: [ {"placeName": "A", ...} ]
    INSTRUCCIONES: Claves en INGLÉS, Valores en ESPAÑOL.
    Plantilla:
    {
      "category": "Lugar/Comida/Otro",
      "placeName": "Nombre",
      "estimatedLocation": "Ciudad, País",
      "priceRange": "Precio",
      "summary": "Qué dice el video sobre esto",
      "score": 5,
      "confidenceLevel": "Alto",
      "criticalVerdict": "Opinión del video",
      "isTouristTrap": false
    }
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
        
        # 1. VERIFICAR EN MAPS (Nombre Oficial)
        maps_data = verify_location_with_maps(guessed_name, guessed_loc)
        
        final_name = maps_data["officialName"] if maps_data else guessed_name
        final_loc = maps_data["address"] if maps_data else guessed_loc

        # 2. INVESTIGAR EN WEB (Detective) - Solo si tenemos un nombre válido
        web_verdict = ""
        is_trap_confirmed = False
        if final_name != "Desconocido":
            web_verdict = check_reputation_with_google(final_name, final_loc)
            # Si el detective dice palabras clave, marcamos bandera roja
            if "trampa" in web_verdict.lower() or "estafa" in web_verdict.lower() or "cuidado" in web_verdict.lower():
                is_trap_confirmed = True

        # Mezclar resumen del video + veredicto web
        video_summary = str(item.get("summary") or "")
        combined_summary = video_summary
        if web_verdict:
            combined_summary = f"{video_summary}\n\n[🕵️‍♂️ Web Check]: {web_verdict}"

        safe_record = {
            "id": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "category": str(item.get("category") or "Otro"),
            "placeName": final_name,
            "estimatedLocation": final_loc,
            "priceRange": str(item.get("priceRange") or "??"),
            "summary": combined_summary, # Resumen Enriquecido
            "score": item.get("score") or 0,
            "confidenceLevel": str(item.get("confidenceLevel") or "Bajo"),
            "criticalVerdict": str(item.get("criticalVerdict") or ""),
            "isTouristTrap": is_trap_confirmed or bool(item.get("isTouristTrap")),
            "fileName": "Video TikTok"
        }
        final_results.append(safe_record)

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
    try: raw = sheet.get_all_records() if sheet else LOCAL_DB
    except: raw = LOCAL_DB
    clean = [r for r in raw if isinstance(r, dict)]
    return jsonify(clean)

@app.route('/api/history', methods=['POST'])
def save_history():
    try:
        new_items = request.json
        if not isinstance(new_items, list): new_items = [new_items]
        sheet = get_db_connection()
        if not sheet: return jsonify({"status": "local"})

        try: existing_records = sheet.get_all_records()
        except: existing_records = []

        name_map = {}
        for i, record in enumerate(existing_records):
            name = str(record.get('placeName', '')).strip().lower()
            if name: name_map[name] = i + 2

        rows_to_create = [] 
        updates_log = []    

        for item in new_items:
            new_name = str(item.get('placeName', '')).strip()
            key = new_name.lower()

            if key in name_map:
                row_idx = name_map[key]
                try: old_record = existing_records[row_idx - 2]
                except: old_record = {}
                try: old_score = float(old_record.get('score') or 0)
                except: old_score = 0
                try: new_score = float(item.get('score') or 0)
                except: new_score = 0
                final_score = new_score if old_score == 0 else round((old_score + new_score) / 2, 1)

                old_summary = str(old_record.get('summary') or "")
                new_summary = str(item.get('summary') or "")
                date_str = time.strftime("%d/%m")
                
                # Evitar duplicar el web check si ya está
                if new_summary not in old_summary:
                    final_summary = f"{old_summary}\n\n[➕ {date_str}]: {new_summary}"[:4500]
                else: final_summary = old_summary

                try:
                    sheet.update_cell(row_idx, 5, final_score)
                    sheet.update_cell(row_idx, 7, final_summary)
                    updates_log.append(new_name)
                except: pass
            else:
                row = [
                    item.get('id'), item.get('timestamp'), item.get('placeName'),
                    item.get('category'), item.get('score'), item.get('estimatedLocation'),
                    item.get('summary'), item.get('fileName')
                ]
                rows_to_create.append(row)

        if len(rows_to_create) > 0:
            try: sheet.append_rows(rows_to_create)
            except: return jsonify({"error": "Fallo guardado"}), 500

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

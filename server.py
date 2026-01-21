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

# --- CONFIGURACIÓN INICIAL ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY") 

print("🚀 INICIANDO: BICHIBICHI SERVER (MODO JUEZ IMPLACABLE)...", flush=True)

if not API_KEY: print("❌ FATAL: API_KEY no encontrada.", flush=True)
else:
    try: genai.configure(api_key=API_KEY)
    except Exception as e: print(f"❌ Error Gemini Config: {e}", flush=True)

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# --- CONEXIÓN A BASE DE DATOS (GOOGLE SHEETS) ---
def get_db_connection():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    if not creds_json or not sheet_id: return None
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), ['https://www.googleapis.com/auth/spreadsheets'])
        return gspread.authorize(creds).open_by_key(sheet_id).sheet1
    except: return None

# --- FUNCIONES AUXILIARES DE FOTOS Y MAPAS ---
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

def verify_location_hybrid(place_name, location_hint, ai_lat=None, ai_lng=None):
    final_lat = ai_lat
    final_lng = ai_lng
    final_address = f"{place_name}, {location_hint}"
    
    if not final_lat or not final_lng or final_lat == 0:
        headers = { 'User-Agent': 'BichibichiApp/2.0', 'Accept-Language': 'es-ES' }
        try:
            time.sleep(1.0) 
            q = f"{place_name} {location_hint}"
            res = requests.get("https://nominatim.openstreetmap.org/search", params={'q': q, 'format': 'json', 'limit': 1}, headers=headers, timeout=4)
            data = res.json()
            if data:
                final_lat = float(data[0].get('lat'))
                final_lng = float(data[0].get('lon'))
                final_address = data[0].get('display_name')
        except: pass

    photo_url = get_unsplash_photo(f"{place_name} {location_hint} travel")
    
    if final_lat and final_lng and final_lat != 0: 
        maps_link = f"https://www.google.com/maps/search/?api=1&query={final_lat},{final_lng}"
    else: 
        safe = urllib.parse.quote(f"{place_name} {location_hint}")
        maps_link = f"https://www.google.com/maps/search/?api=1&query={safe}"
        
    return { "officialName": place_name, "address": final_address, "lat": final_lat, "lng": final_lng, "photoUrl": photo_url, "mapsLink": maps_link }

def process_single_item(item):
    try:
        guessed_name = str(item.get("placeName") or "Desconocido")
        guessed_loc = str(item.get("estimatedLocation") or "")
        
        def clean_coord(val):
            try: return float(str(val).replace(',', '.'))
            except: return 0.0
            
        ai_lat = clean_coord(item.get("lat", 0))
        ai_lng = clean_coord(item.get("lng", 0))
        geo_data = verify_location_hybrid(guessed_name, guessed_loc, ai_lat, ai_lng)
        raw_cat = str(item.get("category") or "Otros")
        
        # Juntamos el juicio crítico con el resumen para que se vea en la tarjeta
        raw_summary = str(item.get("summary") or "")
        critical_verdict = str(item.get("criticalVerdict") or "")
        
        # Si hay juicio crítico, lo ponemos primero en negrita (simulado para texto plano)
        final_summary = raw_summary
        if critical_verdict and critical_verdict not in raw_summary:
            final_summary = f"VEREDICTO: {critical_verdict}. {raw_summary}"
        
        return {
            "id": str(uuid.uuid4()), 
            "timestamp": int(time.time() * 1000), 
            "category": raw_cat, 
            "placeName": geo_data["officialName"],
            "estimatedLocation": geo_data["address"], 
            "priceRange": str(item.get("priceRange") or "N/A"), 
            "summary": final_summary, 
            "score": float(item.get("score") or 4.0),
            "isTouristTrap": bool(item.get("isTouristTrap")), 
            "fileName": "Video TikTok", 
            "photoUrl": geo_data["photoUrl"], 
            "mapsLink": geo_data["mapsLink"], 
            "lat": geo_data["lat"], 
            "lng": geo_data["lng"], 
            "confidenceLevel": "Alto", 
            "criticalVerdict": critical_verdict, 
            "realRating": 0, 
            "website": "", 
            "openNow": ""
        }
    except: return None

# --- DESCARGA DE VIDEO ---
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

# --- ANÁLISIS CON GEMINI (MODO JUEZ) ---
def analyze_with_gemini(video_path):
    print(f"📤 Subiendo a Gemini...", flush=True)
    video_file = genai.upload_file(path=video_path)
    
    while video_file.state.name == "PROCESSING": 
        time.sleep(1)
        video_file = genai.get_file(video_file.name)
        
    model = genai.GenerativeModel(model_name="gemini-2.5-flash")
    
    # --- PROMPT CRÍTICO ---
    prompt = """
    Analiza este video de viajes.
    
    ERES UN CRÍTICO DE VIAJES EXPERTO Y ESCÉPTICO.
    NO repitas como loro lo que dice el Tiktoker. Tu trabajo es JUZGAR si vale la pena.
    
    1. CATEGORÍA (ELIGE SOLO UNA):
       [Naturaleza, Cultura, Gastronomía, Aventura, Alojamiento, Compras, Urbano, Servicios]
    
    2. SCORE (1.0 a 5.0):
       - Si parece publicidad engañosa o "Tourist Trap", castiga la nota (bájala).
       - Si el lugar se ve sucio, lleno o caro, baja la nota aunque el Tiktoker sonría.
       - Si no hay nota, INFIERE una basada en la CALIDAD REAL que ves en el video. NUNCA 0.
       
    3. SUMMARY (Tu Veredicto):
       - No describas solo "qué es". Di si vale la pena.
       - Ej: "Aunque el video dice que es barato, el menú muestra precios de aeropuerto. Se ve sobrevalorado."
       
    4. ¿ES TRAMPA TURÍSTICA? (isTouristTrap):
       - True si: Es solo para fotos de Instagram, es carísimo sin razón, o la comida se ve plástica.
       - False si: Es auténtico, buen precio/calidad.

    OUTPUT JSON:
    [{
      "category": "Gastronomía", 
      "placeName": "Restaurante X", 
      "estimatedLocation": "Lima, Perú", 
      "lat": -12.046, 
      "lng": -77.042, 
      "priceRange": "$50 USD (Caro)", 
      "summary": "El Tiktoker dice que es el mejor sushi, pero el arroz se ve masacote y el lugar está vacío. Parece trampa para turistas.", 
      "score": 2.5, 
      "isTouristTrap": true,
      "criticalVerdict": "Sobrevalorado y posiblemente pagado"
    }]
    """
    
    try:
        response = model.generate_content([video_file, prompt], generation_config={"response_mime_type": "application/json"})
        raw_data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
    except: raw_data = []
    
    try: genai.delete_file(video_file.name)
    except: pass
    
    if isinstance(raw_data, dict): raw_data = [raw_data]
    
    final_results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(process_single_item, raw_data))
        final_results = [r for r in results if r is not None]
        
    return final_results

# --- RUTAS DE LA API ---

@app.route('/analyze', methods=['POST'])
def analyze_video_route():
    try:
        data = request.json
        url = data.get('url') if isinstance(data, dict) else data[0].get('url')
        video_path = download_video(url)
        if not video_path: return jsonify({"error": "Error descarga"}), 500
        results = analyze_with_gemini(video_path)
        return jsonify(results) 
    except Exception as e: return jsonify({"error": str(e)}), 500
    finally: gc.collect()

@app.route('/api/chat', methods=['POST'])
def chat_guide():
    try:
        data = request.json
        user_message = data.get('message', '')
        sheet = get_db_connection()
        if not sheet: return jsonify({"reply": "No puedo acceder a tu base de datos."})
        raw_places = sheet.get_all_records()
        places_context = []
        for p in raw_places:
            places_context.append(f"- {p.get('placeName')} ({p.get('category')}): {p.get('summary')} Score: {p.get('score')}")
        places_str = "\n".join(places_context[-50:])

        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        prompt = f"""
        Actúa como un Guía de Viajes SINCERO llamado "Bichibichi Guide".
        TIENES ACCESO A ESTOS LUGARES:
        {places_str}
        USUARIO: "{user_message}"
        MISIÓN: Responde con honestidad. Si un lugar tiene mala nota en la lista, adviértele al usuario.
        """
        response = model.generate_content(prompt)
        return jsonify({"reply": response.text})
    except Exception as e:
        print(f"Error chat: {e}")
        return jsonify({"reply": "Error en el chat."})

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
                try: lat_val = float(str(r.get('lat', 0)).replace(',', '.'))
                except: lat_val = 0.0
                try: lng_val = float(str(r.get('lng', 0)).replace(',', '.'))
                except: lng_val = 0.0
                clean.append({
                    "id": str(r.get('id') or uuid.uuid4()), 
                    "placeName": str(r.get('placename') or "Lugar"), 
                    "estimatedLocation": str(r.get('estimatedlocation') or ""),
                    "category": str(r.get('category') or "General"), 
                    "score": r.get('score') or 0, 
                    "summary": str(r.get('summary') or ""),
                    "photoUrl": str(r.get('photourl') or ""), 
                    "mapsLink": str(r.get('mapslink') or ""), 
                    "isTouristTrap": str(r.get('istouristtrap')).lower() == 'true',
                    "priceRange": str(r.get('pricerange') or "N/A"), 
                    "lat": lat_val, 
                    "lng": lng_val
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
                    item.get('id'), item.get('timestamp'), item.get('placeName'), item.get('category'), item.get('score'), 
                    item.get('estimatedLocation'), item.get('summary'), item.get('fileName'), item.get('photoUrl'), 
                    item.get('mapsLink'), item.get('website') or "", 0, item.get('isTouristTrap'), item.get('priceRange'), item.get('lat'), item.get('lng')
                ])
        if rows: sheet.append_rows(rows)
        return jsonify({"status": "saved"})
    except: return jsonify({"error": "save"}), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path): return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__': 
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

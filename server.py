import os
import time
import json
import glob
import tempfile
import uuid
import requests
import gc
import traceback
import shutil
import mimetypes
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

print("🚀 INICIANDO: BICHIBICHI SERVER (v5.0 - TANQUE DE GUERRA)...", flush=True)

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

# --- FUNCIONES AUXILIARES ---
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
        headers = { 'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1', 'Accept-Language': 'es-ES' }
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
        raw_summary = str(item.get("summary") or "")
        critical_verdict = str(item.get("criticalVerdict") or "")
        
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
            "realRating": 1, 
            "website": "", 
            "openNow": ""
        }
    except: return None

# --- DESCARGA ROBUSTA (VIDEOS Y FOTOS) ---
def download_video(url):
    print(f"⬇️ Intentando descargar: {url}", flush=True)
    temp_dir = tempfile.mkdtemp()
    
    # IMPORTANTE: No usamos extensión fija para que acepte jpg, mp3, mp4, etc.
    tmpl = os.path.join(temp_dir, f'media_{int(time.time())}.%(ext)s')
    
    # Configuración base común
    opts_base = { 
        'format': 'best', # Intenta bajar la mejor calidad de lo que sea
        'outtmpl': tmpl, 
        'quiet': True, 
        'no_warnings': True, 
        'nocheckcertificate': True,
        'socket_timeout': 30,
        'ignoreerrors': True, # Si una foto falla, que siga con las otras
    }

    # 1. INTENTO CON COOKIES
    if os.path.exists('cookies.txt'):
        print("🍪 Intento 1: Usando Cookies...", flush=True)
        opts_cookies = opts_base.copy()
        opts_cookies['cookiefile'] = 'cookies.txt'
        opts_cookies['http_headers'] = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        
        try:
            with yt_dlp.YoutubeDL(opts_cookies) as ydl: ydl.download([url])
            files = glob.glob(os.path.join(temp_dir, 'media_*'))
            if files: return files
        except Exception as e:
            print(f"⚠️ Intento 1 falló (403/Cookies): {e}", flush=True)
    
    # Pausa de seguridad para evitar saturar
    time.sleep(2)

    # 2. INTENTO "DESKTOP" LIMPIO (Sin cookies, pero como PC)
    # Cambiamos a User-Agent de PC porque el de iPhone a veces falla con galerías de fotos
    print("💻 Intento 2: Modo Desktop Limpio (Fallback)...", flush=True)
    opts_desktop = opts_base.copy()
    opts_desktop['http_headers'] = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'}
    
    try:
        with yt_dlp.YoutubeDL(opts_desktop) as ydl: ydl.download([url])
        files = glob.glob(os.path.join(temp_dir, 'media_*'))
        gc.collect()
        if files: return files
    except Exception as e:
        print(f"❌ Intento 2 falló: {e}", flush=True)

    # Limpieza si todo falla
    shutil.rmtree(temp_dir, ignore_errors=True)
    return None

# --- FUNCIÓN DE ANÁLISIS CON AUTO-REINTENTO (ANTI 429) ---
def analyze_with_gemini_retry(file_paths_list):
    max_retries = 1
    for attempt in range(max_retries + 1):
        try:
            return analyze_with_gemini_core(file_paths_list)
        except Exception as e:
            err_str = str(e)
            # Si el error es de cuota (429), esperamos y reintentamos
            if "429" in err_str or "quota" in err_str.lower():
                if attempt < max_retries:
                    print(f"⏳ Límite de velocidad alcanzado. Esperando 30 segundos...", flush=True)
                    time.sleep(30)
                    print(f"🔄 Reintentando ahora...", flush=True)
                    continue
            # Si es otro error, lanzamos
            raise e

def analyze_with_gemini_core(file_paths_list):
    print(f"📤 Subiendo {len(file_paths_list)} archivos a Gemini...", flush=True)
    uploaded_files = []
    
    try:
        for path in file_paths_list:
            # Filtro estricto de extensiones permitidas
            if not path.lower().endswith(('.mp4', '.jpg', '.jpeg', '.png', '.webp', '.mp3', '.m4a', '.wav')): continue

            # Detección y corrección de MIME TYPES
            mime_type, _ = mimetypes.guess_type(path)
            if not mime_type:
                ext = path.lower().split('.')[-1]
                if ext in ['jpg', 'jpeg']: mime_type = 'image/jpeg'
                elif ext == 'png': mime_type = 'image/png'
                elif ext == 'webp': mime_type = 'image/webp'
                elif ext == 'mp4': mime_type = 'video/mp4'
                elif ext == 'mp3': mime_type = 'audio/mpeg'
                elif ext == 'm4a': mime_type = 'audio/mp4'
                else: mime_type = 'application/octet-stream'
            
            f = genai.upload_file(path=path, mime_type=mime_type)
            
            # Espera activa
            attempts = 0
            while f.state.name == "PROCESSING": 
                time.sleep(1)
                f = genai.get_file(f.name)
                attempts += 1
                if attempts > 30: break
            
            if f.state.name == "ACTIVE": uploaded_files.append(f)

        if not uploaded_files: raise Exception("No se pudieron subir archivos válidos.")

        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        
        prompt = """
        Analiza estos archivos (video, o imágenes + audio) de un viaje.
        ERES UN CRÍTICO DE VIAJES EXPERTO.
        INSTRUCCIONES CLAVE (RESPONDE SOLO EN ESPAÑOL):
        1. UBICACIÓN (CRÍTICO): Extrae coordenadas latitud (lat) y longitud (lng) aproximadas. NO PONGAS 0.
        2. CATEGORÍA: [Naturaleza, Cultura, Gastronomía, Aventura, Alojamiento, Compras, Urbano, Servicios]
        3. SCORE (1.0 a 5.0): Infiere nota si no existe.
        4. SUMMARY: Veredicto honesto y detallado en ESPAÑOL. Si son fotos de texto, LEE LA INFORMACIÓN.
        5. isTouristTrap: True/False.
        OUTPUT JSON: [{"category": "...", "placeName": "...", "estimatedLocation": "...", "lat": -33.45, "lng": -70.66, "priceRange": "...", "summary": "...", "score": 4.0, "isTouristTrap": false, "criticalVerdict": "..."}]
        """
        
        content_payload = uploaded_files + [prompt]
        response = model.generate_content(content_payload, generation_config={"response_mime_type": "application/json"})
        raw_data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
        
        # Limpieza de archivos en la nube
        for f in uploaded_files:
            try: genai.delete_file(f.name)
            except: pass
            
        return raw_data
        
    except Exception as e:
        # Limpieza de emergencia
        for f in uploaded_files:
            try: genai.delete_file(f.name)
            except: pass
        raise e

# --- RUTAS ---
@app.route('/analyze', methods=['POST'])
def analyze_video_route():
    try:
        data = request.json
        raw_url = data.get('url') if isinstance(data, dict) else data[0].get('url')
        url = raw_url.split('?')[0] # Limpieza
        
        # Mantenemos el fix de URL para fotos, suele ayudar
        if '/photo/' in url: url = url.replace('/photo/', '/video/')
        
        print(f"📡 Recibida petición: {url}", flush=True)
        
        files_list = download_video(url)
        if not files_list: return jsonify({"error": "No se pudo descargar el contenido."}), 500
        
        # Usamos la versión con reintento automático
        results_raw = analyze_with_gemini_retry(files_list)
        
        # Procesamos resultados (hilos para geolocalización)
        if isinstance(results_raw, dict): results_raw = [results_raw]
        final_results = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(process_single_item, results_raw))
            final_results = [r for r in results if r is not None]
        
        # Limpieza local final
        try: shutil.rmtree(os.path.dirname(files_list[0]), ignore_errors=True)
        except: pass

        if not final_results: return jsonify({"error": "No se encontraron lugares."}), 422
             
        return jsonify(final_results) 
        
    except Exception as e: 
        print(f"❌ Error Servidor: {str(e)}", flush=True)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally: gc.collect()

@app.route('/api/chat', methods=['POST'])
def chat_guide():
    try:
        data = request.json
        user_message = data.get('message', '')
        sheet = get_db_connection()
        if not sheet: return jsonify({"reply": "Error DB."})
        raw_places = sheet.get_all_records()
        places_context = []
        for p in raw_places:
            places_context.append(f"- {p.get('placeName')} ({p.get('category')}): {p.get('summary')} Score: {p.get('score')}")
        places_str = "\n".join(places_context[-50:])
        model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        prompt = f"Guía Bichibichi (ESPAÑOL). DATA: {places_str}. USER: {user_message}."
        response = model.generate_content(prompt)
        return jsonify({"reply": response.text})
    except: return jsonify({"reply": "Error chat."})

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
                    "id": str(r.get('id')), "placeName": str(r.get('placename')), "estimatedLocation": str(r.get('estimatedlocation')),
                    "category": str(r.get('category')), "score": r.get('score'), "summary": str(r.get('summary')),
                    "photoUrl": str(r.get('photourl')), "mapsLink": str(r.get('mapslink')), "isTouristTrap": str(r.get('istouristtrap')).lower() == 'true',
                    "priceRange": str(r.get('pricerange')), "lat": r.get('lat'), "lng": r.get('lng')
                })
            return jsonify(clean)
        except: return jsonify([])

    try: 
        new_items = request.json
        if not isinstance(new_items, list): new_items = [new_items]
        if not sheet: return jsonify({"status": "local"})
        existing = sheet.get_all_records()
        name_map = {str(r.get('placeName', '')).strip().lower(): i+2 for i, r in enumerate(existing)}
        rows_to_append = []
        for item in new_items:
            key = str(item.get('placeName', '')).strip().lower()
            new_score = float(item.get('score', 0))
            if key in name_map:
                row_idx = name_map[key]
                print(f"🔄 Actualizando: {key}", flush=True)
                curr_record = existing[row_idx - 2]
                try: old_score = float(curr_record.get('score', 0) or 0)
                except: old_score = 0.0
                try: count = int(curr_record.get('realReviews', 0) or 1)
                except: count = 1
                if count == 0: count = 1
                new_count = count + 1
                final_avg = ((old_score * count) + new_score) / new_count
                sheet.update_cell(row_idx, 5, round(final_avg, 1))
                sheet.update_cell(row_idx, 12, new_count)
            else:
                rows_to_append.append([
                    item.get('id'), item.get('timestamp'), item.get('placeName'), item.get('category'), item.get('score'), 
                    item.get('estimatedLocation'), item.get('summary'), item.get('fileName'), item.get('photoUrl'), 
                    item.get('mapsLink'), item.get('website') or "", 1, item.get('isTouristTrap'), item.get('priceRange'), item.get('lat'), item.get('lng')
                ])
        if rows_to_append: sheet.append_rows(rows_to_append)
        return jsonify({"status": "saved"})
    except: return jsonify({"error": "save"}), 500

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(app.static_folder + '/' + path): return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__': 
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))

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

# --- CONFIGURACIÓN ---
load_dotenv()
API_KEY = os.getenv("API_KEY")
UNSPLASH_KEY = os.getenv("UNSPLASH_ACCESS_KEY") 

print("🚀 INICIANDO: GEMINI 2.5 FLASH + FORMATO /0...", flush=True)

if not API_KEY: print("❌ FATAL: API_KEY no encontrada.", flush=True)
else:
    try: genai.configure(api_key=API_KEY)
    except Exception as e: print(f"❌ Error Gemini Config: {e}", flush=True)

app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# --- 1. MODELO (AHORA SÍ: 2.5 FLASH) ---
def get_best_model():
    return "gemini-2.5-flash"

# --- 2. FOTOS (UNSPLASH) ---
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

# --- 3. LÓGICA DE UBICACIÓN ---
def verify_location_hybrid(place_name, location_hint, ai_lat=None, ai_lng=None):
    
    final_lat = ai_lat
    final_lng = ai_lng
    final_address = f"{place_name}, {location_hint}"
    
    # Si la IA falló (0.0), intentamos OSM
    if not final_lat or not final_lng or final_lat == 0:
        headers = { 'User-Agent': 'TravelHunterApp/2.0', 'Accept-Language': 'es-ES' }
        try:
            time.sleep(1.0) 
            q = f"{place_name} {location_hint}"
            res = requests.get("https://nominatim.openstreetmap.org/search", 
                             params={'q': q, 'format': 'json', 'limit': 1}, 
                             headers=headers, timeout=4)
            data = res.json()
            if data:
                final_lat = float(data[0].get('lat'))
                final_lng = float(data[0].get('lon'))
                final_address = data[0].get('display_name')
        except: pass

    # Foto
    photo_url = get_unsplash_photo(f"{place_name} {location_hint} travel")
    
    # --- LA CORRECCIÓN CRÍTICA PARA TU FRONTEND ---
    # Tu frontend hace: link.split('/0')
    # Por eso el link DEBE tener "/0" antes de los números.
    if final_lat and final_lng and final_lat != 0:
        maps_link = f"https://www.google.com/maps/place/...{final_lat},{final_lng}"
    else:

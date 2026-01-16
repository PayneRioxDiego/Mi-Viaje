import os
import time
import json
import glob
import tempfile
import uuid
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

# Gemini
if not API_KEY: print("❌ ERROR: API_KEY not found.")
try: genai.configure(api_key=API_KEY)
except Exception as e: print(f"❌ Error Gemini: {e}")

# Flask
app = Flask(__name__, static_folder='dist', static_url_path='')
CORS(app)

# Memoria Local
LOCAL_DB = []

# --- GOOGLE SHEETS ---
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

# --- DESCARGA ---
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
        return files[0] if files else None
    except Exception as e:
        print(f"❌ Error descarga: {e}")
        return None

# --- ANALISIS ---
def analyze_with_gemini(video_path):
    print(f"📤 Subiendo a Gemini...")
    try:
        video_file = genai.upload_file(path=video_path)
        while video_file.state.name == "PROCESSING":
            time.sleep(1)
            video_file = genai.get_file(video_file.name)
    except Exception as e:
        raise Exception(f"Error subida Gemini: {e}")

    print("🤖 Analizando...")
    # Usamos 1.5 Flash que es muy estable
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    
    prompt = """
    Analiza este video de viaje.
    Responde ÚNICAMENTE con un JSON válido. No uses bloques de código markdown.
    Usa estas claves exactas:
    {
      "category": "Lugar/Comida/Otro",
      "placeName": "Nombre del lugar o ciudad",
      "estimatedLocation": "Ciudad, País",
      "priceRange": "Precio estimado",
      "summary": "Resumen corto y atractivo",
      "score": 5,
      "confidenceLevel": "Alto",
      "criticalVerdict": "Opinión honesta",
      "isTouristTrap": false
    }
    """

import os
import time
import json
import glob
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
import yt_dlp
import google.generativeai as genai
from dotenv import load_dotenv

# Load API Key
load_dotenv()
API_KEY = os.getenv("API_KEY")

if not API_KEY:
    print("❌ ERROR: API_KEY not found in environment variables.")

# Configure Gemini
genai.configure(api_key=API_KEY)

app = Flask(__name__)
# Enable CORS for All Origins (needed so your phone/Vercel can hit this backend)
CORS(app)

def download_video(url):
    """Downloads video using yt-dlp to a temporary file."""
    temp_dir = tempfile.mkdtemp()
    timestamp = int(time.time())
    output_template = os.path.join(temp_dir, f'video_{timestamp}.%(ext)s')

    ydl_opts = {
        'format': 'worst[ext=mp4]', # Low quality is fine for AI analysis, faster download
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Find the downloaded file
        files = glob.glob(os.path.join(temp_dir, 'video_*'))
        if files:
            return files[0]
        return None
    except Exception as e:
        print(f"Download Error: {e}")
        return None

def analyze_with_gemini(video_path):
    """Uploads video to Gemini and analyzes it."""
    print(f"Uploading {video_path} to Gemini...")
    
    # 1. Upload File
    video_file = genai.upload_file(path=video_path)
    
    # 2. Wait for processing
    while video_file.state.name == "PROCESSING":
        print("Waiting for video processing...")
        time.sleep(2)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name == "FAILED":
        raise Exception("Video processing failed.")

    # 3. Generate Content
    # We use gemini-1.5-flash for speed and video capabilities
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    
    prompt = """
    Actúa como un crítico de viajes escéptico y profesional. Analiza el video buscando inconsistencias.
    
    Extrae la información en formato JSON estricto:
    {
      "category": "Lugar" | "Comida" | "Actividad" | "Consejo" | "Otro",
      "placeName": "Nombre exacto",
      "estimatedLocation": "Ciudad, País",
      "priceRange": "Precio estimado",
      "summary": "Resumen de 1 frase",
      "score": 1-5 (Integer),
      "confidenceLevel": "Alto" | "Medio" | "Bajo",
      "criticalVerdict": "Justificación escéptica corta",
      "isTouristTrap": boolean
    }
    """

    print("Generating analysis...")
    response = model.generate_content(
        [video_file, prompt],
        generation_config={
            "response_mime_type": "application/json"
        }
    )

    # Cleanup: Delete file from Gemini Cloud to save storage
    genai.delete_file(video_file.name)
    
    return json.loads(response.text)

@app.route('/analyze', methods=['POST'])
def analyze_video():
    data = request.json
    url = data.get('url')

    if not url:
        return jsonify({"error": "No URL provided"}), 400

    print(f"Processing URL: {url}")
    
    video_path = None
    try:
        # 1. Download
        video_path = download_video(url)
        if not video_path:
            return jsonify({"error": "Failed to download video"}), 500

        # 2. Analyze
        analysis_result = analyze_with_gemini(video_path)
        
        return jsonify(analysis_result)

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        # 3. Cleanup Local File
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
            # Try to remove temp dir
            try:
                os.rmdir(os.path.dirname(video_path))
            except:
                pass

# Health check route for Render
@app.route('/', methods=['GET'])
def health_check():
    return "Backend is running!", 200

if __name__ == '__main__':
    # Get PORT from environment (Render sets this automatically)
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Server running on port {port}")
    # Host 0.0.0.0 is crucial for Docker/Cloud accessibility
    app.run(host='0.0.0.0', port=port)
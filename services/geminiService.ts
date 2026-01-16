import { GoogleGenAI, Type, Schema } from "@google/genai";
import { TravelAnalysis, GroundingLink } from "../types";

// Helper to convert File to Base64
const fileToGenerativePart = async (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64String = reader.result as string;
      const base64Content = base64String.split(',')[1];
      resolve(base64Content);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

const wait = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// --- CONFIGURATION ---
const getBackendUrl = () => {
  // 1. Prioridad: Variable inyectada por Vite
  const envUrl = process.env.VITE_API_URL;
  if (envUrl) return envUrl.replace(/\/$/, "");
  
  // 2. Producción: Detección segura a prueba de fallos
  // Verificamos explícitamente si estamos en el navegador y si existe import.meta.env
  let isProd = false;
  try {
    // @ts-ignore
    isProd = import.meta.env?.PROD; 
  } catch (e) {
    isProd = false;
  }
  
  if (isProd) {
    // En producción (dentro del Docker), el backend sirve el frontend.
    // Usamos una cadena vacía para que fetch use la misma URL base relativa.
    return ''; 
  }
  
  // 3. Desarrollo Local (Fallback)
  return 'http://localhost:5000';
};

const BACKEND_URL = getBackendUrl();

// Secondary service function to get Grounding Data (Search + Maps)
const getGroundingInfo = async (ai: GoogleGenAI, query: string): Promise<GroundingLink[]> => {
  try {
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: {
        parts: [{ text: query }]
      },
      config: {
        tools: [
          { googleSearch: {} },
          { googleMaps: {} }
        ],
        // responseMimeType is not allowed when using googleMaps
      }
    });

    const links: GroundingLink[] = [];
    const chunks = response.candidates?.[0]?.groundingMetadata?.groundingChunks;
    
    if (chunks) {
      chunks.forEach((chunk: any) => {
        if (chunk.web) {
          links.push({
            title: chunk.web.title || "Web Result",
            url: chunk.web.uri,
            source: 'search'
          });
        }
        if (chunk.maps) {
          const uri = chunk.maps.desktopUri || chunk.maps.uri;
          if (uri) {
            links.push({
              title: chunk.maps.title || "Google Maps",
              url: uri,
              source: 'map'
            });
          }
        }
      });
    }

    return links;
  } catch (error) {
    console.warn("Grounding check failed:", error);
    return [];
  }
};

// --- CORE ANALYSIS FUNCTION ---
export const analyzeTravelVideo = async (source: File | string): Promise<TravelAnalysis> => {
  const apiKey = process.env.API_KEY;
  
  if (!apiKey) {
    console.warn("Advertencia: API Key no encontrada. Asegúrate de configurar API_KEY o VITE_GOOGLE_API_KEY.");
  }

  // --- PATH 1: URL ANALYSIS (Via Python Backend) ---
  if (typeof source === 'string') {
    try {
      // Si BACKEND_URL está vacío (Prod), la URL será /analyze (relativa)
      const endpoint = `${BACKEND_URL}/analyze`;
      console.log(`📡 Conectando al Backend en: ${endpoint}`);
      console.log(`📝 Procesando URL: ${source}`);
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: source }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || `Error del servidor (${response.status})`);
      }

      const analysisResult = await response.json() as TravelAnalysis;
      
      // Enhance with Grounding (Client Side)
      if (analysisResult.placeName && analysisResult.estimatedLocation && apiKey) {
         const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
         const groundingQuery = `Find details and official website for "${analysisResult.placeName}" located in "${analysisResult.estimatedLocation}".`;
         const links = await getGroundingInfo(ai, groundingQuery);
         analysisResult.groundingLinks = links;
      }
      
      return analysisResult;

    } catch (error: any) {
      console.error("❌ Error de Backend:", error);
      if (error.message.includes("Failed to fetch")) {
        throw new Error(`No se pudo conectar con el servidor Backend. ¿Está encendido?`);
      }
      throw error;
    }
  }

  // --- PATH 2: LOCAL FILE ANALYSIS (Via Client SDK) ---
  if (!apiKey) throw new Error("API Key faltante para análisis local.");

  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
  const base64Data = await fileToGenerativePart(source);

  const schema: Schema = {
    type: Type.OBJECT,
    properties: {
      category: {
        type: Type.STRING,
        enum: ['Lugar', 'Comida', 'Actividad', 'Consejo', 'Otro'],
        description: "The category of the travel content.",
      },
      placeName: {
        type: Type.STRING,
        description: "The exact name of the place found via OCR or audio.",
      },
      estimatedLocation: {
        type: Type.STRING,
        description: "City and Country.",
      },
      priceRange: {
        type: Type.STRING,
        description: "Estimated price found in video visual numbers or audio.",
      },
      summary: {
        type: Type.STRING,
        description: "A concise 1-sentence summary.",
      },
      // New Critical Fields
      score: {
        type: Type.INTEGER,
        description: "Rating from 1 to 5 based on realism and quality.",
      },
      confidenceLevel: {
        type: Type.STRING,
        enum: ["Alto", "Medio", "Bajo"],
        description: "How confident are you that this place is real and the info is accurate?",
      },
      criticalVerdict: {
        type: Type.STRING,
        description: "A short, skeptical justification for the score. E.g. 'Unrealistic prices for the area.'",
      },
      isTouristTrap: {
        type: Type.BOOLEAN,
        description: "True if it seems like a set for influencers or a rip-off.",
      }
    },
    required: ["category", "placeName", "estimatedLocation", "priceRange", "summary", "score", "confidenceLevel", "criticalVerdict", "isTouristTrap"],
  };

  const modelName = 'gemini-3-pro-preview'; 
  
  const promptText = `Actúa como un crítico de viajes escéptico y profesional. Analiza el video buscando inconsistencias. 
  
  Evalúa los siguientes puntos:
  A. Realismo: ¿Los precios mencionados coinciden con la calidad visual de la comida/lugar? (Ej: Langosta a $5 es sospechoso).
  B. Autenticidad: ¿Parece un sitio real o un set puramente para influencers? ¿Está vacío o lleno de locales?
  C. Claridad: ¿Se ve el nombre del lugar o dirección clara?

  Extrae la información básica (Nombre, Ubicación, Precio) Y ADEMÁS califica la recomendación:
  - Puntuacion (1-5)
  - Nivel de Confianza (Alto/Medio/Bajo)
  - Veredicto Crítico (Justifica tu nota)
  - Es Trampa (Detecta si es Tourist Trap)
  
  Responde estrictamente con el JSON solicitado.`;

  const makeRequest = async (retryCount = 0): Promise<TravelAnalysis> => {
    try {
      // Step 1: Video Analysis (Gemini Pro)
      const response = await ai.models.generateContent({
        model: modelName,
        contents: {
          parts: [
            {
              inlineData: {
                mimeType: source.type,
                data: base64Data
              }
            },
            {
              text: promptText
            }
          ]
        },
        config: {
          responseMimeType: "application/json",
          responseSchema: schema,
          systemInstruction: "You are a senior travel data analyst and skeptical critic. You do not believe hype easily. You verify details against visual evidence.",
        }
      });

      const text = response.text;
      if (!text) throw new Error("No response from Gemini");

      const analysisResult = JSON.parse(text) as TravelAnalysis;

      // Step 2: Grounding Check (Gemini Flash 2.5 with Tools)
      if (analysisResult.placeName && analysisResult.estimatedLocation) {
        const groundingQuery = `Find details and official website for "${analysisResult.placeName}" located in "${analysisResult.estimatedLocation}".`;
        const links = await getGroundingInfo(ai, groundingQuery);
        analysisResult.groundingLinks = links;
      }

      return analysisResult;

    } catch (error: any) {
      // Handle Rate Limits (429)
      const isRateLimit = error.message?.includes('429') || 
                          error.status === 429 || 
                          error.toString().includes('Resource has been exhausted');

      if (isRateLimit && retryCount < 1) {
        console.warn("Rate limit hit (429). Waiting 30 seconds before retrying...");
        await wait(30000); 
        return makeRequest(retryCount + 1);
      }

      console.error("Gemini Analysis Error:", error);
      throw error;
    }
  };

  return makeRequest();
};

// --- AGENT AUTONOMOUS MODES ---

/**
 * 1. Brain: Generates search queries based on user intent.
 */
export const generateSearchStrategy = async (userDescription: string): Promise<string[]> => {
  const apiKey = process.env.API_KEY;
  if (!apiKey) throw new Error("No API Key");
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

  const response = await ai.models.generateContent({
    model: 'gemini-3-pro-preview',
    contents: `Eres un experto estratega de viajes. Basado en este perfil de usuario: "${userDescription}", genera una lista de 5 búsquedas específicas y optimizadas para encontrar las mejores recomendaciones (joyas ocultas, comida, lugares).
    
    Incluye variaciones como "mejores X", "X barato", "X vs Y", "trampas turísticas en X".
    
    Devuelve SOLO una lista de strings en formato JSON (Array de Strings). Ejemplo: ["query 1", "query 2"]`,
    config: {
      responseMimeType: "application/json",
      responseSchema:  {
        type: Type.ARRAY,
        items: { type: Type.STRING }
      }
    }
  });

  return JSON.parse(response.text || "[]");
};

/**
 * 2. Crawler: Simulates "watching" a video by using Google Search Grounding to find a place matching the query
 * and analyzing it with the "Skeptical Critic" persona.
 */
export const executeAutonomousStep = async (query: string): Promise<TravelAnalysis> => {
  const apiKey = process.env.API_KEY;
  if (!apiKey) throw new Error("No API Key");
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

  // Use Gemini 3 Pro with Search to find a result and analyze it immediately
  const response = await ai.models.generateContent({
    model: 'gemini-3-pro-preview',
    contents: `SEARCH GOAL: "${query}"
    
    1. Use Google Search to find ONE specific, real place/restaurant/activity that matches this search goal perfectly.
    2. Act as the "Skeptical Critic". Analyze the search results (reviews, snippets).
    3. Fill out the JSON schema for this place.
    
    If it looks like a tourist trap based on the search results, mark it as such.`,
    config: {
      tools: [{ googleSearch: {} }],
      responseMimeType: "application/json",
      // We reuse the same strict schema so it fits our DB
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          category: { type: Type.STRING, enum: ['Lugar', 'Comida', 'Actividad', 'Consejo', 'Otro'] },
          placeName: { type: Type.STRING },
          estimatedLocation: { type: Type.STRING },
          priceRange: { type: Type.STRING },
          summary: { type: Type.STRING },
          score: { type: Type.INTEGER },
          confidenceLevel: { type: Type.STRING, enum: ["Alto", "Medio", "Bajo"] },
          criticalVerdict: { type: Type.STRING },
          isTouristTrap: { type: Type.BOOLEAN }
        },
        required: ["category", "placeName", "estimatedLocation", "priceRange", "summary", "score", "confidenceLevel", "criticalVerdict", "isTouristTrap"],
      }
    }
  });

  const analysis = JSON.parse(response.text || "{}") as TravelAnalysis;

  // Add grounding links manually from the search result if available
  const chunks = response.candidates?.[0]?.groundingMetadata?.groundingChunks;
  const links: GroundingLink[] = [];
  if (chunks) {
    chunks.forEach((chunk: any) => {
      if (chunk.web) links.push({ title: chunk.web.title, url: chunk.web.uri, source: 'search' });
    });
  }
  analysis.groundingLinks = links;

  return analysis;
};
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
export const getBackendUrl = () => {
  // 1. CRÍTICO PARA CLOUD RUN:
  // Si estamos en producción (build), forzamos ruta relativa vacía ('').
  // Esto hace que las peticiones vayan a "/api/history" en el MISMO dominio donde está la web.
  // @ts-ignore
  if (import.meta.env.PROD) {
    return '';
  }

  // 2. Desarrollo Local: Usar variable de entorno o fallback
  const envUrl = process.env.VITE_API_URL;
  if (envUrl) return envUrl.replace(/\/$/, "");

  // 3. Fallback final para local
  return 'http://localhost:5000';
};

export const API_BASE_URL = getBackendUrl();

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
    console.warn("Advertencia: API Key no encontrada.");
  }

  // --- PATH 1: URL ANALYSIS (Via Python Backend) ---
  if (typeof source === 'string') {
    try {
      const endpoint = `${API_BASE_URL}/analyze`;
      console.log(`📡 Conectando al Backend en: ${endpoint}`);
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
      },
      placeName: { type: Type.STRING },
      estimatedLocation: { type: Type.STRING },
      priceRange: { type: Type.STRING },
      summary: { type: Type.STRING },
      score: { type: Type.INTEGER },
      confidenceLevel: {
        type: Type.STRING,
        enum: ["Alto", "Medio", "Bajo"],
      },
      criticalVerdict: { type: Type.STRING },
      isTouristTrap: { type: Type.BOOLEAN }
    },
    required: ["category", "placeName", "estimatedLocation", "priceRange", "summary", "score", "confidenceLevel", "criticalVerdict", "isTouristTrap"],
  };

  const modelName = 'gemini-3-pro-preview'; 
  
  const promptText = `Actúa como un crítico de viajes escéptico y profesional. Analiza el video buscando inconsistencias. 
  
  Evalúa los siguientes puntos:
  A. Realismo: ¿Los precios mencionados coinciden con la calidad visual de la comida/lugar?
  B. Autenticidad: ¿Parece un sitio real o un set puramente para influencers?
  C. Claridad: ¿Se ve el nombre del lugar o dirección clara?

  Extrae la información básica y califica la recomendación.
  Responde estrictamente con el JSON solicitado.`;

  const makeRequest = async (retryCount = 0): Promise<TravelAnalysis> => {
    try {
      const response = await ai.models.generateContent({
        model: modelName,
        contents: {
          parts: [
            { inlineData: { mimeType: source.type, data: base64Data } },
            { text: promptText }
          ]
        },
        config: {
          responseMimeType: "application/json",
          responseSchema: schema,
        }
      });

      const text = response.text;
      if (!text) throw new Error("No response from Gemini");

      const analysisResult = JSON.parse(text) as TravelAnalysis;

      if (analysisResult.placeName && analysisResult.estimatedLocation) {
        const groundingQuery = `Find details and official website for "${analysisResult.placeName}" located in "${analysisResult.estimatedLocation}".`;
        const links = await getGroundingInfo(ai, groundingQuery);
        analysisResult.groundingLinks = links;
      }

      return analysisResult;

    } catch (error: any) {
      const isRateLimit = error.message?.includes('429');
      if (isRateLimit && retryCount < 1) {
        await wait(30000); 
        return makeRequest(retryCount + 1);
      }
      throw error;
    }
  };

  return makeRequest();
};

export const generateSearchStrategy = async (userDescription: string): Promise<string[]> => {
  const apiKey = process.env.API_KEY;
  if (!apiKey) throw new Error("No API Key");
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

  const response = await ai.models.generateContent({
    model: 'gemini-3-pro-preview',
    contents: `Eres un experto estratega de viajes. Basado en: "${userDescription}", genera 5 búsquedas optimizadas para Google Search. Devuelve JSON array strings.`,
    config: {
      responseMimeType: "application/json",
      responseSchema: { type: Type.ARRAY, items: { type: Type.STRING } }
    }
  });

  return JSON.parse(response.text || "[]");
};

export const executeAutonomousStep = async (query: string): Promise<TravelAnalysis> => {
  const apiKey = process.env.API_KEY;
  if (!apiKey) throw new Error("No API Key");
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

  const response = await ai.models.generateContent({
    model: 'gemini-3-pro-preview',
    contents: `SEARCH GOAL: "${query}". Find ONE real place. Analyze critically.`,
    config: {
      tools: [{ googleSearch: {} }],
      responseMimeType: "application/json",
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
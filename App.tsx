import React, { useState } from 'react';
import { Upload, Search, MapPin, AlertTriangle, Loader2, ExternalLink, Star, Globe, Clock } from 'lucide-react';

// 1. DEFINICIÓN DE TIPOS (Actualizada con los nuevos campos del servidor)
interface TravelAnalysis {
  id: string;
  category: string;
  placeName: string;
  estimatedLocation: string;
  priceRange: string;
  summary: string;
  score: number;
  confidenceLevel: string;
  criticalVerdict: string;
  isTouristTrap: boolean;
  // Nuevos campos visuales
  photoUrl?: string;
  realRating?: number;
  realReviews?: number;
  website?: string;
  mapsLink?: string;
  openNow?: string;
}

function App() {
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<TravelAnalysis[]>([]);
  const [error, setError] = useState('');

  // Lógica para analizar
  const handleAnalyze = async () => {
    if (!url) return;
    setLoading(true);
    setError('');
    setResults([]);

    try {
      // Ajusta la URL si tu backend está en otro puerto/dominio
      const response = await fetch('/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) throw new Error('Error al conectar con el servidor');
      
      const data = await response.json();
      // Si devuelve error el backend
      if (data.error) throw new Error(data.error);

      // Si es un array lo guardamos, si es objeto lo metemos en array
      const dataArray = Array.isArray(data) ? data : [data];
      setResults(dataArray);

      // Guardado automático en el historial (Batch)
      try {
        await fetch('/api/history', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(dataArray)
        });
      } catch (e) {
        console.warn("No se pudo guardar en el historial", e);
      }

    } catch (err: any) {
      setError(err.message || 'Ocurrió un error inesperado');
    } finally {
      setLoading(false);
    }
  };

  // Helper para colores del Score
  const getScoreColor = (score: number) => {
    if (score >= 4.5) return 'bg-emerald-100 text-emerald-700 border-emerald-200';
    if (score >= 3.5) return 'bg-blue-100 text-blue-700 border-blue-200';
    return 'bg-amber-100 text-amber-700 border-amber-200';
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans p-6">
      <div className="max-w-5xl mx-auto">
        
        {/* HEADER */}
        <header className="mb-10 text-center">
          <h1 className="text-4xl font-extrabold text-slate-800 tracking-tight mb-2">
            ✈️ Travel Hunter AI
          </h1>
          <p className="text-slate-500">
            Descubre la verdad de los videos de viaje. Sin filtros.
          </p>
        </header>

        {/* INPUT SECTION */}
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 mb-8 max-w-2xl mx-auto">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Pega el enlace de TikTok / Instagram / Shorts
          </label>
          <div className="flex gap-3">
            <div className="relative flex-grow">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search className="h-5 w-5 text-slate-400" />
              </div>
              <input
                type="text"
                className="block w-full pl-10 pr-3 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
                placeholder="https://www.tiktok.com/@usuario/video..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </div>
            <button
              onClick={handleAnalyze}
              disabled={loading || !url}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-lg shadow-blue-200"
            >
              {loading ? <Loader2 className="animate-spin h-5 w-5" /> : <Upload className="h-5 w-5" />}
              Analizar
            </button>
          </div>
          {error && (
            <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm flex items-center gap-2">
              <AlertTriangle className="h-4 w-4" />
              {error}
            </div>
          )}
        </div>

        {/* RESULTS GRID (AQUÍ ESTÁ LA NUEVA MAGIA VISUAL) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {results.map((item) => (
            <div 
              key={item.id} 
              className="bg-white rounded-2xl shadow-lg border border-slate-100 overflow-hidden hover:shadow-xl transition-all duration-300 flex flex-col"
            >
              {/* 1. IMAGEN DEL LUGAR (Header) */}
              <div className="relative h-56 bg-slate-200 group">
                {item.photoUrl ? (
                  <img 
                    src={item.photoUrl} 
                    alt={item.placeName} 
                    className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-slate-400 bg-slate-100">
                    <span className="text-sm font-medium">Sin foto disponible</span>
                  </div>
                )}
                
                {/* Badge Trampa */}
                {item.isTouristTrap && (
                  <div className="absolute top-3 right-3 bg-red-600 text-white text-xs font-bold px-3 py-1.5 rounded-full shadow-md flex items-center gap-1 animate-pulse">
                    <AlertTriangle className="h-3 w-3" /> TRAMPA
                  </div>
                )}

                {/* Badge Precio */}
                <div className="absolute bottom-3 left-3 bg-black/60 backdrop-blur-md text-white text-xs font-medium px-3 py-1 rounded-lg border border-white/20">
                  💰 {item.priceRange}
                </div>
              </div>

              {/* 2. CONTENIDO */}
              <div className="p-6 flex flex-col flex-grow">
                
                {/* Título y Score */}
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <span className="text-xs font-bold text-blue-600 uppercase tracking-wider mb-1 block">
                      {item.category}
                    </span>
                    <h3 className="text-xl font-bold text-slate-800 leading-snug">
                      {item.placeName}
                    </h3>
                    <div className="flex items-center text-slate-500 text-sm mt-1 gap-1">
                      <MapPin className="h-3 w-3" />
                      {item.estimatedLocation}
                    </div>
                  </div>
                  
                  <div className={`flex flex-col items-center justify-center px-3 py-1.5 rounded-xl border ${getScoreColor(item.score)}`}>
                    <span className="text-lg font-bold leading-none">{item.score}</span>
                    <span className="text-[10px] opacity-80 font-medium">PUNTOS</span>
                  </div>
                </div>

                {/* Datos Reales de Google (Si existen) */}
                {(item.realRating || item.openNow) && (
                  <div className="flex flex-wrap gap-3 mb-4 text-xs text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    {item.realRating && (
                      <span className="flex items-center gap-1">
                        <Star className="h-3 w-3 text-amber-400 fill-amber-400" />
                        <span className="font-semibold">{item.realRating}</span>
                        <span className="text-slate-400">({item.realReviews})</span>
                      </span>
                    )}
                    {item.openNow && (
                      <span className="flex items-center gap-1 border-l border-slate-200 pl-3">
                        <Clock className="h-3 w-3 text-slate-400" />
                        <span>{item.openNow}</span>
                      </span>
                    )}
                  </div>
                )}

                {/* Resumen */}
                <div className="prose prose-sm text-slate-600 mb-5 flex-grow">
                  <p className="line-clamp-4 whitespace-pre-line text-sm leading-relaxed">
                    {item.summary.replace(/\[.*?\]:/g, '') /* Limpiamos etiquetas técnicas visualmente */}
                  </p>
                </div>

                {/* Veredicto Crítico */}
                {item.criticalVerdict && (
                  <div className="bg-amber-50 border-l-4 border-amber-300 p-3 mb-5 rounded-r-lg">
                    <p className="text-xs text-amber-800 italic">
                      "{item.criticalVerdict}"
                    </p>
                  </div>
                )}

                {/* 3. BOTONES DE ACCIÓN (Footer) */}
                <div className="grid grid-cols-2 gap-3 mt-auto pt-4 border-t border-slate-100">
                  {item.mapsLink ? (
                    <a 
                      href={item.mapsLink} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center justify-center gap-2 px-4 py-2.5 bg-blue-50 text-blue-700 rounded-xl text-sm font-semibold hover:bg-blue-100 transition-colors"
                    >
                      <MapPin className="h-4 w-4" />
                      Ver Mapa
                    </a>
                  ) : (
                     <button disabled className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-50 text-slate-400 rounded-xl text-sm font-semibold cursor-not-allowed">
                       <MapPin className="h-4 w-4" /> Sin Mapa
                     </button>
                  )}

                  {item.website ? (
                    <a 
                      href={item.website} 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-50 text-slate-700 rounded-xl text-sm font-semibold hover:bg-slate-100 transition-colors border border-slate-200"
                    >
                      <Globe className="h-4 w-4" />
                      Web
                    </a>
                  ) : (
                    <button disabled className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-50 text-slate-300 rounded-xl text-sm font-semibold cursor-not-allowed border border-slate-100">
                      <Globe className="h-4 w-4" /> No Web
                    </button>
                  )}
                </div>

              </div>
            </div>
          ))}
        </div>

        {/* EMPTY STATE */}
        {!loading && results.length === 0 && !error && (
          <div className="text-center py-20 text-slate-400">
            <div className="bg-slate-100 h-20 w-20 rounded-full flex items-center justify-center mx-auto mb-4">
              <Search className="h-8 w-8 text-slate-300" />
            </div>
            <p className="text-lg">Pega un link arriba para comenzar a descubrir.</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

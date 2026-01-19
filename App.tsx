import React, { useState } from 'react';
import { Upload, Search, MapPin, AlertTriangle, Loader2, Star, Globe, Clock, ChevronRight, Camera } from 'lucide-react';

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

  const handleAnalyze = async () => {
    if (!url) return;
    setLoading(true);
    setError('');
    setResults([]);

    try {
      const response = await fetch('/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) throw new Error('Error de conexión');
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      const dataArray = Array.isArray(data) ? data : [data];
      setResults(dataArray);

      // Guardar en background
      fetch('/api/history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dataArray)
      }).catch(() => {});

    } catch (err: any) {
      setError(err.message || 'Error inesperado');
    } finally {
      setLoading(false);
    }
  };

  const getScoreBadge = (score: number) => {
    if (score >= 4.5) return 'bg-emerald-400 text-white shadow-emerald-200';
    if (score >= 3.5) return 'bg-blue-400 text-white shadow-blue-200';
    return 'bg-amber-400 text-white shadow-amber-200';
  };

  return (
    <div className="min-h-screen bg-[#F3F5F9] font-sans text-slate-800 selection:bg-purple-100">
      
      {/* BACKGROUND DECORATION */}
      <div className="fixed top-0 left-0 w-full h-96 bg-gradient-to-b from-indigo-50 to-[#F3F5F9] -z-10" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        
        {/* HEADER AMIGABLE */}
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="inline-flex items-center justify-center p-3 bg-white rounded-2xl shadow-sm mb-4">
            <span className="text-2xl mr-2">✈️</span>
            <span className="font-bold text-slate-700 tracking-tight">Travel Hunter</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-black text-slate-800 tracking-tight mb-4">
            Descubre tu próxima <br/>
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">
              aventura real
            </span>
          </h1>
          <p className="text-lg text-slate-500">
            Analizamos videos de redes sociales para decirte qué vale la pena y qué es una trampa.
          </p>
        </div>

        {/* INPUT DE BÚSQUEDA FLOTANTE */}
        <div className="max-w-3xl mx-auto mb-16 relative z-10">
          <div className="bg-white p-2 rounded-3xl shadow-xl shadow-indigo-100/50 flex flex-col sm:flex-row items-center border border-slate-100">
            <div className="flex-grow w-full relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <Search className="h-5 w-5 text-indigo-300" />
              </div>
              <input
                type="text"
                className="w-full pl-11 pr-4 py-4 rounded-2xl border-none focus:ring-0 text-slate-700 placeholder:text-slate-300 text-lg"
                placeholder="Pega aquí el link de TikTok o Instagram..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </div>
            <button
              onClick={handleAnalyze}
              disabled={loading || !url}
              className="w-full sm:w-auto mt-2 sm:mt-0 bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-4 rounded-2xl font-bold transition-all transform hover:scale-105 active:scale-95 disabled:opacity-70 disabled:scale-100 flex items-center justify-center gap-2 shadow-lg shadow-indigo-200"
            >
              {loading ? <Loader2 className="animate-spin h-5 w-5" /> : 'Analizar Magia ✨'}
            </button>
          </div>
          {error && (
            <div className="mt-4 text-center text-red-500 bg-red-50 py-2 px-4 rounded-xl inline-block mx-auto w-full">
              {error}
            </div>
          )}
        </div>

        {/* GRID DE RESULTADOS (MASONRY STYLE) */}
        {results.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {results.map((item) => (
              <div 
                key={item.id} 
                className="group bg-white rounded-[2rem] overflow-hidden shadow-lg shadow-slate-200/50 hover:shadow-2xl hover:shadow-indigo-200/50 transition-all duration-300 hover:-translate-y-2 border border-slate-100"
              >
                
                {/* 1. IMAGEN HERO (ALTO IMPACTO) */}
                <div className="relative h-72 overflow-hidden">
                  {item.photoUrl ? (
                    <img 
                      src={item.photoUrl} 
                      alt={item.placeName} 
                      className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                    />
                  ) : (
                    <div className="w-full h-full bg-slate-100 flex flex-col items-center justify-center text-slate-300">
                      <Camera className="h-12 w-12 mb-2 opacity-50" />
                      <span className="font-medium">Sin foto disponible</span>
                    </div>
                  )}

                  {/* GRADIENTE SUPERIOR PARA LEER TEXTO */}
                  <div className="absolute top-0 left-0 w-full h-24 bg-gradient-to-b from-black/50 to-transparent pointer-events-none" />

                  {/* BADGES FLOTANTES */}
                  <div className="absolute top-4 left-4 right-4 flex justify-between items-start">
                    <span className="bg-white/90 backdrop-blur-md text-slate-800 text-xs font-bold px-3 py-1.5 rounded-full uppercase tracking-wider shadow-sm">
                      {item.category}
                    </span>
                    {item.isTouristTrap && (
                      <span className="bg-red-500 text-white text-xs font-bold px-3 py-1.5 rounded-full shadow-lg animate-pulse flex items-center gap-1">
                        <AlertTriangle className="h-3 w-3" /> TRAMPA
                      </span>
                    )}
                  </div>

                  {/* SCORE STICKER */}
                  <div className={`absolute bottom-4 right-4 h-14 w-14 rounded-full flex flex-col items-center justify-center shadow-lg border-2 border-white ${getScoreBadge(item.score)}`}>
                    <span className="text-lg font-black leading-none">{item.score}</span>
                    <span className="text-[9px] font-bold opacity-90">PTS</span>
                  </div>
                </div>

                {/* 2. CONTENIDO CARD */}
                <div className="p-6 relative">
                  
                  {/* Info Rápida (Maps) */}
                  {(item.realRating || item.openNow) && (
                    <div className="flex gap-3 mb-3 text-xs font-medium text-slate-400">
                      {item.realRating && (
                        <span className="flex items-center gap-1 bg-amber-50 text-amber-700 px-2 py-1 rounded-lg">
                          <Star className="h-3 w-3 fill-amber-500 text-amber-500" />
                          {item.realRating} ({item.realReviews})
                        </span>
                      )}
                      {item.openNow && (
                        <span className={`flex items-center gap-1 px-2 py-1 rounded-lg ${item.openNow.includes('Abierto') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                          <Clock className="h-3 w-3" />
                          {item.openNow.split(' ')[0]}
                        </span>
                      )}
                    </div>
                  )}

                  <h3 className="text-2xl font-black text-slate-800 mb-1 leading-tight group-hover:text-indigo-600 transition-colors">
                    {item.placeName}
                  </h3>
                  
                  <div className="flex items-center text-slate-400 text-sm mb-4">
                    <MapPin className="h-4 w-4 mr-1" />
                    <span className="truncate">{item.estimatedLocation}</span>
                  </div>

                  {/* Resumen con estilo */}
                  <div className="bg-slate-50 p-4 rounded-2xl mb-5">
                    <p className="text-slate-600 text-sm leading-relaxed line-clamp-4">
                      {item.summary.split('[🕵️‍♂️ Web]:')[0]}
                    </p>
                  </div>

                  {/* Veredicto Web (Si existe) */}
                  {item.summary.includes('[🕵️‍♂️ Web]:') && (
                    <div className="mb-5 flex items-start gap-3 p-3 bg-indigo-50 rounded-xl border border-indigo-100">
                      <div className="bg-indigo-100 p-1.5 rounded-full shrink-0">
                        <Search className="h-4 w-4 text-indigo-600" />
                      </div>
                      <p className="text-xs text-indigo-800 italic leading-relaxed">
                        {item.summary.split('[🕵️‍♂️ Web]:')[1]}
                      </p>
                    </div>
                  )}

                  {/* FOOTER DE ACCIONES */}
                  <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                    <div className="text-xs font-bold text-slate-300 uppercase tracking-widest">
                      {item.priceRange === '??' ? 'Precio N/A' : item.priceRange}
                    </div>
                    
                    <div className="flex gap-2">
                      {item.website && (
                        <a href={item.website} target="_blank" rel="noreferrer" className="p-2.5 bg-slate-100 text-slate-500 rounded-xl hover:bg-slate-200 transition-colors">
                          <Globe className="h-5 w-5" />
                        </a>
                      )}
                      {item.mapsLink ? (
                        <a 
                          href={item.mapsLink} 
                          target="_blank" 
                          rel="noreferrer" 
                          className="flex items-center gap-2 px-5 py-2.5 bg-slate-900 text-white rounded-xl text-sm font-bold hover:bg-black transition-all shadow-md hover:shadow-lg"
                        >
                          Ir al Mapa <ChevronRight className="h-4 w-4" />
                        </a>
                      ) : (
                        <button disabled className="px-5 py-2.5 bg-slate-100 text-slate-300 rounded-xl text-sm font-bold cursor-not-allowed">
                          Sin Mapa
                        </button>
                      )}
                    </div>
                  </div>

                </div>
              </div>
            ))}
          </div>
        )}

        {/* EMPTY STATE AMIGABLE */}
        {!loading && results.length === 0 && (
          <div className="text-center py-24 opacity-60">
            <div className="inline-block p-6 bg-white rounded-full shadow-lg mb-4 rotate-12">
              <span className="text-4xl">🌍</span>
            </div>
            <p className="text-slate-400 font-medium">Esperando tu próximo destino...</p>
          </div>
        )}

      </div>
    </div>
  );
}
export default App;

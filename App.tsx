import React, { useState, useEffect } from 'react';
import { Upload, Search, MapPin, AlertTriangle, Loader2, Globe, ChevronRight, Camera, History } from 'lucide-react';

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
  const [history, setHistory] = useState<TravelAnalysis[]>([]); // Estado para el historial
  const [error, setError] = useState('');

  // 1. CARGAR HISTORIAL AL INICIO
  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const response = await fetch('/api/history');
      if (response.ok) {
        const data = await response.json();
        // Invertimos para ver los más recientes primero
        setHistory(data.reverse());
      }
    } catch (e) {
      console.error("Error cargando historial", e);
    }
  };

  const handleAnalyze = async () => {
    if (!url) return;
    setLoading(true);
    setError('');
    // No borramos results anteriores inmediatamente para evitar "parpadeo" feo
    
    try {
      const response = await fetch('/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) throw new Error('Error de conexión con el servidor');
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      const dataArray = Array.isArray(data) ? data : [data];
      
      // Actualizamos resultados actuales
      setResults(dataArray);
      
      // Guardamos en historial (Backend)
      await fetch('/api/history', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(dataArray)
      });
      
      // Recargamos historial para verlo abajo
      fetchHistory();

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

  // Componente de Tarjeta para reutilizar en Resultado e Historial
  const TravelCard = ({ item }: { item: TravelAnalysis }) => (
    <div className="group bg-white rounded-[2rem] overflow-hidden shadow-lg shadow-slate-200/50 hover:shadow-2xl hover:shadow-indigo-200/50 transition-all duration-300 border border-slate-100 flex flex-col h-full">
      <div className="relative h-64 overflow-hidden shrink-0">
        {item.photoUrl ? (
          <img src={item.photoUrl} alt={item.placeName} className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" />
        ) : (
          <div className="w-full h-full bg-slate-100 flex flex-col items-center justify-center text-slate-300">
            <Camera className="h-12 w-12 mb-2 opacity-50" />
            <span className="font-medium text-xs">Sin foto</span>
          </div>
        )}
        <div className="absolute top-0 left-0 w-full h-24 bg-gradient-to-b from-black/50 to-transparent pointer-events-none" />
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
        <div className={`absolute bottom-4 right-4 h-12 w-12 rounded-full flex flex-col items-center justify-center shadow-lg border-2 border-white ${getScoreBadge(item.score)}`}>
          <span className="text-base font-black leading-none">{item.score}</span>
        </div>
      </div>

      <div className="p-6 flex flex-col flex-grow">
        <h3 className="text-xl font-black text-slate-800 mb-1 leading-tight group-hover:text-indigo-600 transition-colors">
          {item.placeName}
        </h3>
        <div className="flex items-center text-slate-400 text-xs mb-4">
          <MapPin className="h-3 w-3 mr-1" />
          <span className="truncate">{item.estimatedLocation}</span>
        </div>

        <div className="bg-slate-50 p-4 rounded-2xl mb-4 flex-grow">
          <p className="text-slate-600 text-xs leading-relaxed line-clamp-4 hover:line-clamp-none transition-all cursor-pointer">
            {item.summary.split('[🕵️‍♂️ Web]:')[0]}
          </p>
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-slate-100 mt-auto">
          <div className="text-[10px] font-bold text-slate-300 uppercase tracking-widest">
            {item.priceRange === '??' ? 'N/A' : item.priceRange}
          </div>
          <div className="flex gap-2">
            {item.mapsLink ? (
              <a href={item.mapsLink} target="_blank" rel="noreferrer" className="flex items-center gap-1 px-4 py-2 bg-slate-900 text-white rounded-xl text-xs font-bold hover:bg-black transition-all shadow-md">
                Mapa <ChevronRight className="h-3 w-3" />
              </a>
            ) : (
              <span className="px-4 py-2 bg-slate-100 text-slate-300 rounded-xl text-xs font-bold cursor-not-allowed">Sin Mapa</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-[#F3F5F9] font-sans text-slate-800 selection:bg-purple-100 pb-20">
      <div className="fixed top-0 left-0 w-full h-96 bg-gradient-to-b from-indigo-50 to-[#F3F5F9] -z-10" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* HEADER */}
        <div className="text-center max-w-2xl mx-auto mb-12">
          <div className="inline-flex items-center justify-center p-3 bg-white rounded-2xl shadow-sm mb-4">
            <span className="text-2xl mr-2">✈️</span>
            <span className="font-bold text-slate-700 tracking-tight">Travel Hunter</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-black text-slate-800 tracking-tight mb-4">
            Descubre la verdad
          </h1>
          <p className="text-lg text-slate-500">Pega un link de TikTok o Instagram y analizaremos si es una joya o una trampa.</p>
        </div>

        {/* BUSCADOR */}
        <div className="max-w-3xl mx-auto mb-16 relative z-10">
          <div className="bg-white p-2 rounded-3xl shadow-xl shadow-indigo-100/50 flex flex-col sm:flex-row items-center border border-slate-100">
            <div className="flex-grow w-full relative">
              <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                <Search className="h-5 w-5 text-indigo-300" />
              </div>
              <input
                type="text"
                className="w-full pl-11 pr-4 py-4 rounded-2xl border-none focus:ring-0 text-slate-700 placeholder:text-slate-300 text-lg"
                placeholder="https://www.tiktok.com/..."
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </div>
            <button
              onClick={handleAnalyze}
              disabled={loading || !url}
              className="w-full sm:w-auto mt-2 sm:mt-0 bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-4 rounded-2xl font-bold transition-all transform hover:scale-105 active:scale-95 disabled:opacity-70 disabled:scale-100 flex items-center justify-center gap-2 shadow-lg shadow-indigo-200"
            >
              {loading ? <Loader2 className="animate-spin h-5 w-5" /> : 'Analizar'}
            </button>
          </div>
          {error && <div className="mt-4 text-center text-red-500 bg-red-50 py-2 px-4 rounded-xl inline-block mx-auto w-full">{error}</div>}
        </div>

        {/* RESULTADOS ACTUALES */}
        {results.length > 0 && (
          <div className="mb-16 animate-fade-in-up">
            <div className="flex items-center gap-2 mb-6">
              <span className="bg-indigo-600 w-2 h-8 rounded-full"></span>
              <h2 className="text-2xl font-black text-slate-800">Resultado del Análisis</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              {results.map((item) => <TravelCard key={item.id} item={item} />)}
            </div>
          </div>
        )}

        {/* HISTORIAL (GALERÍA) */}
        {history.length > 0 && (
          <div className="border-t border-slate-200 pt-12">
            <div className="flex items-center gap-2 mb-8 opacity-60">
              <History className="h-6 w-6" />
              <h2 className="text-2xl font-black text-slate-800">Tus Descubrimientos Anteriores</h2>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 opacity-90">
              {history.map((item) => <TravelCard key={`hist-${item.id}`} item={item} />)}
            </div>
          </div>
        )}
        
        {/* EMPTY STATE TOTAL */}
        {!loading && results.length === 0 && history.length === 0 && (
          <div className="text-center py-12 opacity-40">
            <p>Aún no hay viajes guardados.</p>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;

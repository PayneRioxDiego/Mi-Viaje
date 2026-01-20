import React, { useState, useEffect, useRef } from 'react';
import { Search, MapPin, AlertTriangle, Loader2, ChevronRight, Camera, Grid, Map as MapIcon, Layers, MessageCircle, Send } from 'lucide-react';
import MapComponent from './MapComponent'; 

interface TravelAnalysis {
  id: string; category: string; placeName: string; estimatedLocation: string;
  priceRange: string; summary: string; score: number; confidenceLevel: string;
  criticalVerdict: string; isTouristTrap: boolean; photoUrl?: string;
  realRating?: number; realReviews?: number; website?: string; mapsLink?: string;
  openNow?: string; lat?: number; lng?: number;
}

// Interfaz para el chat
interface ChatMessage {
  role: 'user' | 'bot';
  text: string;
}

function App() {
  const [activeTab, setActiveTab] = useState<'analyze' | 'cards' | 'map' | 'chat'>('analyze');
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<TravelAnalysis[]>([]);
  const [history, setHistory] = useState<TravelAnalysis[]>([]);
  const [error, setError] = useState('');
  
  // Estados del Chat
  const [messages, setMessages] = useState<ChatMessage[]>([{role: 'bot', text: '¡Hola! Soy tu Guía de Viajes. Conozco todos los lugares que has guardado. Pregúntame por una ruta, recomendaciones o qué visitar primero. 🗺️'}]);
  const [inputMsg, setInputMsg] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { fetchHistory(); }, []);
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const fetchHistory = async () => {
    try {
      const response = await fetch('/api/history');
      if (response.ok) {
        const data = await response.json();
        const safeData = data.map((item: any) => ({
            ...item,
            id: item.id || Math.random().toString(36).substr(2, 9),
            lat: typeof item.lat === 'string' ? parseFloat(item.lat) : item.lat,
            lng: typeof item.lng === 'string' ? parseFloat(item.lng) : item.lng
        }));
        setHistory(safeData.reverse());
      }
    } catch (e) { console.error("Error cargando historial", e); }
  };

  const handleAnalyze = async () => {
    if (!url) return;
    setLoading(true); setError('');
    try {
      const response = await fetch('/analyze', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }),
      });
      if (!response.ok) throw new Error('Error de conexión');
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      const dataArray = Array.isArray(data) ? data : [data];
      setResults(dataArray);
      fetch('/api/history', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(dataArray) }).then(() => fetchHistory());
    } catch (err: any) { setError(err.message || 'Error inesperado'); } 
    finally { setLoading(false); }
  };

  const handleSendChat = async () => {
    if (!inputMsg.trim()) return;
    const userText = inputMsg;
    setInputMsg('');
    setMessages(prev => [...prev, { role: 'user', text: userText }]);
    setChatLoading(true);

    try {
        const res = await fetch('/api/chat', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: userText })
        });
        const data = await res.json();
        setMessages(prev => [...prev, { role: 'bot', text: data.reply }]);
    } catch (e) {
        setMessages(prev => [...prev, { role: 'bot', text: 'Ups, se me cayó el mapa. Intenta de nuevo.' }]);
    } finally {
        setChatLoading(false);
    }
  };

  const getScoreBadge = (score: number) => {
    if (score >= 4.5) return 'bg-emerald-400 text-white shadow-emerald-200';
    if (score >= 3.5) return 'bg-blue-400 text-white shadow-blue-200';
    return 'bg-amber-400 text-white shadow-amber-200';
  };

  const TravelCard = ({ item }: { item: TravelAnalysis }) => {
    const safeSummary = item.summary || "";
    const summaryParts = safeSummary.split('[🕵️‍♂️ Web]:');
    const mainSummary = summaryParts[0] || "Sin resumen.";
    return (
      <div className="group bg-white rounded-[2rem] overflow-hidden shadow-lg shadow-slate-200/50 hover:shadow-2xl transition-all duration-300 border border-slate-100 flex flex-col h-full">
        <div className="relative h-56 overflow-hidden shrink-0">
          {item.photoUrl ? ( <img src={item.photoUrl} alt={item.placeName} className="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110" /> ) : ( <div className="w-full h-full bg-slate-100 flex flex-col items-center justify-center text-slate-300"> <Camera className="h-10 w-10 mb-2 opacity-50" /> <span className="font-medium text-[10px]">Sin foto</span> </div> )}
          <div className="absolute top-0 left-0 w-full h-20 bg-gradient-to-b from-black/50 to-transparent pointer-events-none" />
          <div className="absolute top-4 left-4 right-4 flex justify-between items-start">
            <span className="bg-white/90 backdrop-blur-md text-slate-800 text-[10px] font-bold px-2 py-1 rounded-full uppercase tracking-wider shadow-sm">{item.category || "General"}</span>
            {item.isTouristTrap && ( <span className="bg-red-500 text-white text-[10px] font-bold px-2 py-1 rounded-full shadow-lg animate-pulse flex items-center gap-1"> <AlertTriangle className="h-3 w-3" /> TRAMPA </span> )}
          </div>
          <div className={`absolute bottom-3 right-3 h-10 w-10 rounded-full flex flex-col items-center justify-center shadow-lg border-2 border-white ${getScoreBadge(item.score || 0)}`}> <span className="text-sm font-black leading-none">{item.score || 0}</span> </div>
        </div>
        <div className="p-5 flex flex-col flex-grow">
          <h3 className="text-lg font-black text-slate-800 mb-1 leading-tight">{item.placeName || "Desconocido"}</h3>
          <div className="flex items-center text-slate-400 text-xs mb-3"> <MapPin className="h-3 w-3 mr-1" /> <span className="truncate">{item.estimatedLocation || "Ubicación desconocida"}</span> </div>
          <div className="bg-slate-50 p-3 rounded-xl mb-4 flex-grow"> <p className="text-slate-600 text-xs leading-relaxed line-clamp-4">{mainSummary}</p> </div>
          <div className="flex items-center justify-between pt-3 border-t border-slate-100 mt-auto">
            <div className="text-[10px] font-bold text-slate-300 uppercase tracking-widest"> {(!item.priceRange || item.priceRange === '??') ? 'N/A' : item.priceRange} </div>
            {item.mapsLink ? ( <a href={item.mapsLink} target="_blank" rel="noreferrer" className="flex items-center gap-1 px-3 py-1.5 bg-slate-900 text-white rounded-lg text-[10px] font-bold hover:bg-black transition-all shadow-md"> Ver Mapa <ChevronRight className="h-3 w-3" /> </a> ) : null}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-[#F3F5F9] font-sans text-slate-800 pb-20">
      <div className="bg-white/80 backdrop-blur-md sticky top-0 z-[2000] border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2"> 
                <span className="text-2xl">✈️</span> 
                {/* --- NOMBRE ACTUALIZADO --- */}
                <span className="font-bold text-slate-800 tracking-tight hidden sm:inline">Bichibichi Guia Explorador</span> 
            </div>
            <nav className="flex bg-slate-100 p-1 rounded-xl">
              <button onClick={() => setActiveTab('analyze')} className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'analyze' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}> <Search className="h-4 w-4" /> <span className="hidden sm:inline">Analizar</span> </button>
              <button onClick={() => setActiveTab('cards')} className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'cards' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}> <Grid className="h-4 w-4" /> <span className="hidden sm:inline">Mis Hallazgos</span> </button>
              <button onClick={() => setActiveTab('map')} className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'map' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}> <MapIcon className="h-4 w-4" /> <span className="hidden sm:inline">Mapa Mundi</span> </button>
              <button onClick={() => setActiveTab('chat')} className={`px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-all ${activeTab === 'chat' ? 'bg-indigo-600 text-white shadow-md shadow-indigo-300' : 'text-slate-500 hover:text-slate-700'}`}> <MessageCircle className="h-4 w-4" /> <span className="hidden sm:inline">Guía IA</span> </button>
            </nav>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-8">
        {activeTab === 'analyze' && (
          <div className="animate-fade-in">
            <div className="text-center max-w-2xl mx-auto mb-10 mt-8"> <h1 className="text-4xl font-black text-slate-800 tracking-tight mb-3">¿Joya o Trampa?</h1> <p className="text-slate-500">Pega un link de TikTok o Instagram para descubrirlo.</p> </div>
            <div className="max-w-2xl mx-auto mb-12">
              <div className="bg-white p-2 rounded-2xl shadow-xl shadow-indigo-100/50 flex flex-col sm:flex-row items-center border border-slate-100"> <input type="text" className="w-full pl-6 pr-4 py-3 rounded-xl border-none focus:ring-0 text-slate-700 placeholder:text-slate-300" placeholder="https://www.tiktok.com/..." value={url} onChange={(e) => setUrl(e.target.value)} /> <button onClick={handleAnalyze} disabled={loading || !url} className="w-full sm:w-auto mt-2 sm:mt-0 bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-3 rounded-xl font-bold transition-all flex items-center justify-center gap-2 shadow-lg shadow-indigo-200"> {loading ? <Loader2 className="animate-spin h-5 w-5" /> : 'Analizar'} </button> </div>
              {error && <div className="mt-4 text-center text-red-500 bg-red-50 py-2 px-4 rounded-xl">{error}</div>}
            </div>
            {results.length > 0 && <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">{results.map((item) => <TravelCard key={item.id} item={item} />)}</div>}
            {results.length === 0 && !loading && <div className="text-center mt-20 opacity-30"><Layers className="h-16 w-16 mx-auto mb-4" /><p>Esperando tu próximo destino...</p></div>}
          </div>
        )}

        {activeTab === 'cards' && (
          <div className="animate-fade-in">
             <div className="flex items-center justify-between mb-8"> <h2 className="text-2xl font-black text-slate-800">Tu Colección de Viajes</h2> <span className="bg-indigo-100 text-indigo-700 font-bold px-3 py-1 rounded-full text-xs">{history.length} Destinos</span> </div>
             {history.length > 0 ? ( <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"> {history.map((item) => <TravelCard key={`hist-${item.id}`} item={item} />)} </div> ) : ( <div className="text-center py-20 text-slate-400"><p>Aún no has guardado ningún viaje.</p></div> )}
          </div>
        )}

        {activeTab === 'map' && (
          <div className="animate-fade-in h-[calc(100vh-180px)]">
             <div className="h-full w-full rounded-3xl overflow-hidden shadow-2xl border border-slate-200 bg-slate-100"> <MapComponent items={history} /> </div>
          </div>
        )}

        {activeTab === 'chat' && (
          <div className="animate-fade-in max-w-3xl mx-auto h-[calc(100vh-180px)] flex flex-col bg-white rounded-3xl shadow-2xl border border-slate-100 overflow-hidden">
             <div className="bg-indigo-600 p-4 flex items-center gap-3">
                <div className="h-10 w-10 bg-white/20 rounded-full flex items-center justify-center text-white backdrop-blur-sm">🤖</div>
                <div>
                    <h3 className="text-white font-bold">Guía de Viajes IA</h3>
                    <p className="text-indigo-100 text-xs">Experto en tus {history.length} lugares guardados</p>
                </div>
             </div>
             <div className="flex-grow overflow-y-auto p-6 space-y-4 bg-slate-50">
                {messages.map((msg, idx) => (
                    <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div className={`max-w-[80%] px-5 py-3 rounded-2xl text-sm leading-relaxed shadow-sm ${msg.role === 'user' ? 'bg-indigo-600 text-white rounded-br-none' : 'bg-white text-slate-700 border border-slate-200 rounded-bl-none'}`}>
                            <div className="whitespace-pre-wrap">{msg.text}</div>
                        </div>
                    </div>
                ))}
                {chatLoading && (
                    <div className="flex justify-start">
                        <div className="bg-white px-4 py-3 rounded-2xl rounded-bl-none border border-slate-200 shadow-sm flex items-center gap-2">
                            <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />
                            <span className="text-xs text-slate-400">Pensando ruta...</span>
                        </div>
                    </div>
                )}
                <div ref={chatEndRef} />
             </div>
             <div className="p-4 bg-white border-t border-slate-100">
                <div className="flex gap-2">
                    <input 
                        type="text" 
                        value={inputMsg}
                        onChange={(e) => setInputMsg(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleSendChat()}
                        placeholder="Ej: Planea un viaje de 3 días a Cusco..." 
                        className="flex-grow px-4 py-3 rounded-xl bg-slate-100 border-transparent focus:bg-white focus:ring-2 focus:ring-indigo-500 transition-all text-sm"
                    />
                    <button 
                        onClick={handleSendChat}
                        disabled={chatLoading || !inputMsg.trim()}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white p-3 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Send className="h-5 w-5" />
                    </button>
                </div>
             </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

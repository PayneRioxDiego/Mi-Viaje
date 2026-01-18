import React, { useState, useCallback, useEffect } from 'react';
import VideoUploader from './components/VideoUploader';
import AgentPlanner from './components/AgentPlanner';
import ResultCard from './components/ResultCard';
import HistoryTable from './components/HistoryTable';
import { TravelAnalysis, AnalysisStatus, AnalysisHistoryItem } from './types';
import { analyzeTravelVideo, generateSearchStrategy, executeAutonomousStep } from './services/geminiService';
import { SheetManager } from './services/dataManager';

const App: React.FC = () => {
  // Navigation State
  const [activeMode, setActiveMode] = useState<'upload' | 'agent'>('upload');

  // Logic State
  const [status, setStatus] = useState<AnalysisStatus>(AnalysisStatus.IDLE);
  
  // CAMBIO 1: Ahora currentResults es un ARRAY (lista), no un objeto único
  const [currentResults, setCurrentResults] = useState<TravelAnalysis[]>([]); 
  
  const [database, setDatabase] = useState<AnalysisHistoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  
  // Cloud Sync State
  const [isSyncing, setIsSyncing] = useState(false);

  // Agent State
  const [agentLogs, setAgentLogs] = useState<string[]>([]);
  const [isAgentRunning, setIsAgentRunning] = useState(false);

  // Load Database from Cloud (Sheets) on Mount
  useEffect(() => {
    handleForceSync();
  }, []);

  const addLog = (message: string) => {
    setAgentLogs(prev => [...prev, message]);
  };

  // --- CLOUD SYNC HANDLER ---
  const handleForceSync = async () => {
    setIsSyncing(true);
    try {
      const data = await SheetManager.loadData();
      setDatabase(data);
    } catch (e) {
      console.error("Sync failed", e);
      setError("Error al sincronizar con Google Sheets");
    } finally {
      setIsSyncing(false);
    }
  };

  // --- MANUAL UPLOAD HANDLER (MODIFICADO PARA LISTAS) ---
  const handleAnalyze = useCallback(async (source: File | string) => {
    setError(null);
    setCurrentResults([]); // Limpiamos resultados anteriores
    const identifier = typeof source === 'string' ? source : source.name;

    // Check duplication (Opcional: podrías querer permitir re-analizar si trae más lugares)
    // Por ahora lo dejamos pasar para probar la multi-extracción.

    setStatus(AnalysisStatus.PROCESSING);

    try {
      // 1. Obtenemos la LISTA de resultados del Backend
      const rawResults = await analyzeTravelVideo(source);
      
      // Aseguramos que sea un array (por si acaso el backend devuelve uno solo suelto)
      const resultsArray = Array.isArray(rawResults) ? rawResults : [rawResults];

      if (resultsArray.length === 0) {
        throw new Error("La IA no detectó ningún lugar en el video.");
      }

      // 2. Preparamos los objetos para la base de datos (Backend ya trae IDs y Timestamps buenos)
      const newItems: AnalysisHistoryItem[] = resultsArray.map(item => ({
        ...item,
        fileName: identifier // Asignamos el nombre del archivo/url a todos
      }));
      
      // 3. Guardamos TODO el lote en la Nube
      // Nota: SheetManager debe ser capaz de recibir un array, o el backend lo maneja.
      // Como actualizamos el server.py para recibir listas en /api/history, esto funcionará.
      await SheetManager.saveRecord(newItems);
      
      // 4. Actualizamos el estado local
      setDatabase(prev => [...newItems, ...prev]); // Añadimos los nuevos arriba
      setCurrentResults(newItems); // Mostramos las tarjetas nuevas
      setStatus(AnalysisStatus.SUCCESS);

    } catch (err: any) {
      console.error(err);
      setError(err.message || "Ocurrió un error en el análisis.");
      setStatus(AnalysisStatus.ERROR);
    }
  }, [database]);

  // --- AGENT AUTONOMOUS HANDLER ---
  const handleAgentStart = useCallback(async (tripDescription: string) => {
    setIsAgentRunning(true);
    setAgentLogs([]); 
    setError(null);
    addLog(`> INICIALIZANDO AGENTE para: "${tripDescription.substring(0, 30)}..."`);

    try {
      addLog("Generando estrategia de búsqueda con Gemini Pro...");
      const strategies = await generateSearchStrategy(tripDescription);
      addLog(`Estrategia Generada: ${strategies.length} misiones cargadas.`);
      
      for (let i = 0; i < strategies.length; i++) {
        const query = strategies[i];
        const step = i + 1;
        
        addLog(`> [${step}/${strategies.length}] Ejecutando: "${query}"`);
        
        // Deduplication Check
        const db = await SheetManager.loadData();
        const exists = db.some(item => item.fileName === `AGENT_QUERY: ${query}`);

        if (exists) {
           addLog(`Saltando búsqueda duplicada: ${query}`);
           continue;
        }

        try {
           const result = await executeAutonomousStep(query);
           
           // El agente suele devolver 1 resultado por query, pero por seguridad lo tratamos como array si hiciera falta
           const resultArray = Array.isArray(result) ? result : [result];

           for (const res of resultArray) {
             addLog(`  Encontrado: ${res.placeName}`);
             addLog(`  Veredicto: ${res.criticalVerdict}`);
             
             if (res.isTouristTrap) addLog(`  ⚠️ ADVERTENCIA: ¡Trampa Turística!`);
             else addLog(`  ✅ ÉXITO: Recomendación válida.`);

             const newItem: AnalysisHistoryItem = {
               ...res,
               id: crypto.randomUUID(),
               timestamp: Date.now(),
               fileName: `AGENT_QUERY: ${query}` 
             };
             
             await SheetManager.saveRecord(newItem); // Guardamos uno por uno en modo agente
             setDatabase(prev => [newItem, ...prev]); 
           }
           
        } catch (stepErr) {
           addLog(`  ❌ ERROR en paso ${step}: ${stepErr}`);
        }
        
        await new Promise(r => setTimeout(r, 1000));
      }

      addLog("> MISIÓN COMPLETADA.");

    } catch (err: any) {
      addLog(`FALLO CRÍTICO: ${err.message}`);
      setError("El agente falló. Revisa los registros.");
    } finally {
      setIsAgentRunning(false);
    }
  }, []);

  return (
    <div className="min-h-screen pb-20 bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-gradient-to-br from-primary-600 to-fuchsia-600 p-2 rounded-lg shadow-md">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900 tracking-tight leading-none">
                Nuestro <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-fuchsia-600">Viaje</span>
              </h1>
              <p className="text-xs text-slate-500 font-medium">Base de Datos en Nube (Google Sheets)</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            <button
              onClick={handleForceSync}
              disabled={isSyncing}
              className={`flex items-center space-x-2 px-3 py-1.5 rounded-md text-xs font-bold uppercase tracking-wider border transition-all ${
                isSyncing 
                  ? 'bg-slate-100 text-slate-400 border-slate-200 cursor-wait'
                  : 'bg-white text-primary-600 border-primary-200 hover:bg-primary-50 hover:border-primary-300'
              }`}
            >
              <svg className={`w-3 h-3 ${isSyncing ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span>{isSyncing ? 'Sync' : 'Forzar Sync'}</span>
            </button>

            <div className="flex space-x-1 bg-slate-100 p-1 rounded-lg">
               <button 
                 onClick={() => setActiveMode('upload')}
                 className={`px-4 py-1.5 text-sm font-semibold rounded-md transition-all ${activeMode === 'upload' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
               >
                 Subir Video
               </button>
               <button 
                 onClick={() => setActiveMode('agent')}
                 className={`px-4 py-1.5 text-sm font-semibold rounded-md transition-all ${activeMode === 'agent' ? 'bg-white text-primary-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}
               >
                 Agente Auto
               </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        
        <div className="mb-12">
          {activeMode === 'upload' ? (
             <VideoUploader onAnalyze={handleAnalyze} status={status} />
          ) : (
             <AgentPlanner 
                onStartAgent={handleAgentStart} 
                isRunning={isAgentRunning}
                logs={agentLogs}
             />
          )}
        </div>

        {error && (
          <div className="w-full max-w-2xl mx-auto mb-8 p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-start text-amber-800 shadow-sm animate-fade-in">
            <span className="font-medium">{error}</span>
          </div>
        )}

        {/* CAMBIO 2: Renderizado de Múltiples Tarjetas */}
        {activeMode === 'upload' && currentResults.length > 0 && (
          <div className="animate-fade-in-up mb-16">
            <div className="flex items-center space-x-2 mb-6">
              <span className="h-px flex-1 bg-slate-200"></span>
              <span className="text-sm font-bold text-primary-600 uppercase tracking-wider bg-primary-50 px-3 py-1 rounded-full border border-primary-100">
                ✨ {currentResults.length} Lugares Detectados
              </span>
              <span className="h-px flex-1 bg-slate-200"></span>
            </div>
            
            {/* Grid de Tarjetas */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {currentResults.map((item) => (
                <ResultCard key={item.id} data={item} />
              ))}
            </div>
          </div>
        )}

        <div className="relative">
           {isSyncing && (
             <div className="absolute inset-0 bg-white/50 z-10 flex items-start justify-center pt-20">
                <div className="bg-white px-4 py-2 rounded-full shadow-lg border border-slate-100 flex items-center space-x-2">
                   <div className="w-2 h-2 bg-primary-500 rounded-full animate-ping"></div>
                   <span className="text-xs font-bold text-slate-600">Actualizando datos de la nube...</span>
                </div>
             </div>
           )}
           <HistoryTable history={database} />
        </div>
      </main>
    </div>
  );
};

export default App;

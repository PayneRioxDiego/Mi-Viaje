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
  const [currentResult, setCurrentResult] = useState<TravelAnalysis | null>(null);
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

  // --- MANUAL UPLOAD HANDLER ---
  const handleAnalyze = useCallback(async (source: File | string) => {
    setError(null);
    setCurrentResult(null);
    const identifier = typeof source === 'string' ? source : source.name;

    // Check duplication against current loaded DB
    const exists = database.some(item => item.fileName === identifier);
    if (exists) {
      setError(`⚠️ Duplicado Detectado: "${identifier}" ya existe en la base de datos.`);
      setStatus(AnalysisStatus.ERROR);
      return; 
    }

    setStatus(AnalysisStatus.PROCESSING);

    try {
      const result = await analyzeTravelVideo(source);
      const newItem: AnalysisHistoryItem = {
        ...result,
        id: crypto.randomUUID(),
        timestamp: Date.now(),
        fileName: identifier
      };
      
      // Save to Cloud
      const updatedDB = await SheetManager.saveRecord(newItem);
      setDatabase(updatedDB);
      
      setCurrentResult(result);
      setStatus(AnalysisStatus.SUCCESS);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "Ocurrió un error.");
      setStatus(AnalysisStatus.ERROR);
    }
  }, [database]);

  // --- AGENT AUTONOMOUS HANDLER ---
  const handleAgentStart = useCallback(async (tripDescription: string) => {
    setIsAgentRunning(true);
    setAgentLogs([]); // Clear logs
    setError(null);
    addLog(`> INICIALIZANDO AGENTE para: "${tripDescription.substring(0, 30)}..."`);

    try {
      // 1. Generate Strategy
      addLog("Generando estrategia de búsqueda con Gemini Pro...");
      const strategies = await generateSearchStrategy(tripDescription);
      addLog(`Estrategia Generada: ${strategies.length} misiones cargadas.`);
      
      // 2. Execution Loop
      for (let i = 0; i < strategies.length; i++) {
        const query = strategies[i];
        const step = i + 1;
        
        addLog(`> [${step}/${strategies.length}] Ejecutando: "${query}"`);
        
        // Deduplication Check
        const db = await SheetManager.loadData(); // Ensure we have latest for dedup check
        const exists = db.some(item => item.fileName === `AGENT_QUERY: ${query}`);

        if (exists) {
           addLog(`Saltando búsqueda duplicada: ${query}`);
           continue;
        }

        try {
           // Execute Step
           const result = await executeAutonomousStep(query);
           
           addLog(`  Encontrado: ${result.placeName}`);
           addLog(`  Veredicto: ${result.criticalVerdict}`);
           
           if (result.isTouristTrap) {
             addLog(`  ⚠️ ADVERTENCIA: ¡Trampa Turística detectada!`);
           } else {
             addLog(`  ✅ ÉXITO: Recomendación válida.`);
           }

           // Save to Cloud
           const newItem: AnalysisHistoryItem = {
             ...result,
             id: crypto.randomUUID(),
             timestamp: Date.now(),
             fileName: `AGENT_QUERY: ${query}` 
           };
           
           await SheetManager.saveRecord(newItem);
           setDatabase(prev => [newItem, ...prev]); // Optimistic update
           
        } catch (stepErr) {
           addLog(`  ❌ ERROR en paso ${step}: ${stepErr}`);
        }
        
        // Small delay to be polite to the API
        await new Promise(r => setTimeout(r, 1000));
      }

      addLog("> MISIÓN COMPLETADA. Todas las estrategias ejecutadas.");

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
            {/* Force Sync Button */}
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
              <span>{isSyncing ? 'Sincronizando...' : 'Forzar Sync'}</span>
            </button>

            {/* Main Nav Tabs */}
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
        
        {/* Conditional Input View */}
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

        {/* Global Error */}
        {error && (
          <div className="w-full max-w-2xl mx-auto mb-8 p-4 bg-amber-50 border border-amber-200 rounded-lg flex items-start text-amber-800 shadow-sm animate-fade-in">
            <span className="font-medium">{error}</span>
          </div>
        )}

        {/* Single Result View (Only for Manual Upload) */}
        {activeMode === 'upload' && currentResult && (
          <div className="animate-fade-in-up mb-16">
            <div className="flex items-center space-x-2 mb-4">
              <span className="h-px flex-1 bg-slate-200"></span>
              <span className="text-sm font-semibold text-slate-400 uppercase tracking-wider">Último Análisis</span>
              <span className="h-px flex-1 bg-slate-200"></span>
            </div>
            <ResultCard data={currentResult} />
          </div>
        )}

        {/* Database Grid (Always Visible) */}
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
import React, { useState } from 'react';

interface AgentPlannerProps {
  onStartAgent: (description: string) => void;
  isRunning: boolean;
  logs: string[];
}

const AgentPlanner: React.FC<AgentPlannerProps> = ({ onStartAgent, isRunning, logs }) => {
  const [description, setDescription] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (description.trim()) {
      onStartAgent(description);
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto mb-10">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden flex flex-col md:flex-row">
        
        {/* Input Section */}
        <div className="p-8 md:w-1/2 border-b md:border-b-0 md:border-r border-slate-100">
          <div className="mb-6">
            <h3 className="text-xl font-bold text-slate-900 flex items-center">
              <span className="bg-primary-600 text-white p-1.5 rounded-lg mr-2 shadow-sm">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.384-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></svg>
              </span>
              Planificador Autónomo
            </h3>
            <p className="text-sm text-slate-500 mt-2">
              Describe el viaje de tus sueños. La IA generará una estrategia de búsqueda y encontrará los mejores lugares automáticamente.
            </p>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-4">
            <textarea
              className="w-full h-40 p-4 border border-slate-300 rounded-xl bg-slate-50 focus:bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all resize-none text-sm leading-relaxed"
              placeholder="Ejemplo: Voy a Tokio 7 días, presupuesto mochilero. Me gusta la comida picante, tiendas de anime ocultas y evitar trampas turísticas."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              disabled={isRunning}
            />
            <button
              type="submit"
              disabled={isRunning || !description}
              className={`w-full py-3 px-4 rounded-xl font-bold text-white shadow-sm transition-all transform active:scale-[0.98] ${
                isRunning 
                  ? 'bg-slate-400 cursor-not-allowed' 
                  : 'bg-gradient-to-r from-primary-600 to-fuchsia-600 hover:from-primary-700 hover:to-fuchsia-700'
              }`}
            >
              {isRunning ? 'Agente Trabajando...' : 'Iniciar Agente Automático'}
            </button>
          </form>
        </div>

        {/* Console / Log Section */}
        <div className="p-6 md:w-1/2 bg-slate-900 text-slate-300 font-mono text-xs flex flex-col">
          <div className="flex items-center justify-between mb-4 border-b border-slate-700 pb-2">
            <span className="font-bold text-emerald-400">SALIDA DE TERMINAL</span>
            <div className="flex space-x-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-red-500"></div>
              <div className="w-2.5 h-2.5 rounded-full bg-yellow-500"></div>
              <div className="w-2.5 h-2.5 rounded-full bg-green-500"></div>
            </div>
          </div>
          
          <div className="flex-grow overflow-y-auto space-y-2 h-64 md:h-auto custom-scrollbar">
            {logs.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-600 opacity-50">
                 <svg className="w-12 h-12 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                 <p>Esperando comandos...</p>
              </div>
            ) : (
              logs.map((log, index) => (
                <div key={index} className="flex items-start animate-fade-in">
                  <span className="text-slate-600 mr-2">[{new Date().toLocaleTimeString()}]</span>
                  <span className={log.startsWith('>') ? 'text-primary-400 font-bold' : log.includes('ÉXITO') ? 'text-emerald-400' : 'text-slate-300'}>
                    {log}
                  </span>
                </div>
              ))
            )}
            {isRunning && (
               <div className="flex items-center mt-2 text-primary-400">
                 <span className="animate-pulse mr-1">▋</span> Procesando...
               </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default AgentPlanner;
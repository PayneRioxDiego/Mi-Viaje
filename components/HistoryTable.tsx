import React, { useState, useMemo } from 'react';
import { AnalysisHistoryItem } from '../types';

interface HistoryTableProps {
  history: AnalysisHistoryItem[];
}

// --- Helper Functions for Styles & Icons ---

const renderStars = (score: number) => {
  // Ensure score is between 1 and 5
  const clampedScore = Math.max(1, Math.min(5, Math.round(score)));
  return '⭐'.repeat(clampedScore);
};

const getCategoryIcon = (category: string) => {
  switch (category.toLowerCase()) {
    case 'comida': return '🍜';
    case 'actividad': return '🎫';
    case 'lugar': case 'paisaje': return '🏞️';
    case 'consejo': return '💡';
    default: return '✈️';
  }
};

const getCardTheme = (item: AnalysisHistoryItem) => {
  const { score, isTouristTrap, category } = item;
  
  // Critical Logic for Border/Status
  let borderClass = 'border-slate-200';
  let statusBadge = null;

  if (isTouristTrap || score <= 2) {
    borderClass = 'border-red-400 ring-1 ring-red-100';
    statusBadge = (
      <span className="flex items-center text-[10px] font-bold uppercase tracking-wider bg-red-100 text-red-700 px-2 py-1 rounded-full border border-red-200">
        <span className="mr-1">⚠️</span> Cuidado
      </span>
    );
  } else if (score >= 4) {
    borderClass = 'border-emerald-400 ring-1 ring-emerald-50';
    statusBadge = (
      <span className="flex items-center text-[10px] font-bold uppercase tracking-wider bg-emerald-100 text-emerald-700 px-2 py-1 rounded-full border border-emerald-200">
        <span className="mr-1">💎</span> Top Pick / Recomendado
      </span>
    );
  }

  // Category Badge Colors
  let categoryClass = 'bg-slate-100 text-slate-700';
  if (category.toLowerCase() === 'comida') categoryClass = 'bg-orange-100 text-orange-800 border-orange-200';
  else if (category.toLowerCase() === 'actividad') categoryClass = 'bg-green-100 text-green-800 border-green-200';
  else if (category.toLowerCase() === 'lugar') categoryClass = 'bg-blue-100 text-blue-800 border-blue-200';

  return { borderClass, statusBadge, categoryClass, icon: getCategoryIcon(category) };
};

const TravelCard: React.FC<{ item: AnalysisHistoryItem }> = ({ item }) => {
  const theme = getCardTheme(item);
  const isUrl = item.fileName.startsWith('http') || item.fileName.startsWith('AGENT_QUERY');

  return (
    <div className={`group bg-white rounded-2xl p-6 shadow-sm hover:shadow-xl transition-all duration-300 border-2 ${theme.borderClass} flex flex-col h-full relative overflow-hidden`}>
      
      {/* Header */}
      <div className="flex justify-between items-start mb-3 relative z-10">
        <div className="flex items-center space-x-3">
          <span className="text-3xl filter drop-shadow-sm transform group-hover:scale-110 transition-transform">{theme.icon}</span>
          <div>
            <h3 className="font-bold text-slate-900 leading-tight line-clamp-1">{item.placeName}</h3>
            <p className="text-xs text-slate-400 font-medium flex items-center mt-0.5">
              <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
              </svg>
              {item.estimatedLocation}
            </p>
          </div>
        </div>
        {theme.statusBadge}
      </div>

      {/* Star Rating */}
      <div className="mb-4 flex items-center space-x-2">
        <span className="text-sm tracking-widest">{renderStars(item.score || 0)}</span>
        <span className="text-xs text-slate-400 font-medium">
          ({item.score}/5)
        </span>
      </div>

      {/* Critical Verdict */}
      <div className="bg-slate-50 rounded-lg p-3 mb-4 border border-slate-100">
        <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
          Veredicto Crítico IA
        </p>
        <p className={`text-sm italic leading-relaxed ${item.isTouristTrap || (item.score || 0) <= 2 ? 'text-red-700 font-medium' : 'text-slate-600'}`}>
          "{item.criticalVerdict || item.summary}"
        </p>
      </div>

      {/* Tags */}
      <div className="flex flex-wrap gap-2 mb-4 mt-auto">
        <span className={`px-2.5 py-1 rounded-lg text-xs font-bold uppercase tracking-wide border ${theme.categoryClass}`}>
          {item.category}
        </span>
        <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-white text-emerald-700 border border-emerald-200 shadow-sm">
          {item.priceRange}
        </span>
      </div>

      {/* Footer / Actions */}
      <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
        <span className="text-[10px] text-slate-400 font-mono uppercase">
          Confianza: {item.confidenceLevel || 'N/A'}
        </span>
        
        {isUrl ? (
          <a 
            href={item.fileName.startsWith('http') ? item.fileName : '#'}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center text-xs font-bold text-slate-900 hover:text-primary-600 transition-colors bg-slate-100 hover:bg-slate-200 px-3 py-1.5 rounded-full"
            style={{ pointerEvents: item.fileName.startsWith('AGENT_QUERY') ? 'none' : 'auto', opacity: item.fileName.startsWith('AGENT_QUERY') ? 0.5 : 1 }}
          >
            {item.fileName.startsWith('AGENT_QUERY') ? 'Auto Agente' : 'Ver en TikTok'}
            {!item.fileName.startsWith('AGENT_QUERY') && (
              <svg className="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            )}
          </a>
        ) : (
          <span className="text-xs text-slate-300">Archivo Subido</span>
        )}
      </div>
    </div>
  );
};

// --- Main Dashboard Component ---

const HistoryDashboard: React.FC<HistoryTableProps> = ({ history }) => {
  const [categoryFilter, setCategoryFilter] = useState<string>('All');
  const [minScoreFilter, setMinScoreFilter] = useState<number>(0);

  // Extract Categories
  const categories = useMemo(() => {
    const cats = new Set(history.map(h => h.category));
    return ['All', ...Array.from(cats)];
  }, [history]);

  // Filter Data
  const filteredData = useMemo(() => {
    return history.filter(item => {
      const matchCat = categoryFilter === 'All' || item.category === categoryFilter;
      const matchScore = (item.score || 0) >= minScoreFilter;
      return matchCat && matchScore;
    });
  }, [history, categoryFilter, minScoreFilter]);

  if (history.length === 0) return null;

  return (
    <div className="w-full max-w-7xl mx-auto mt-16 animate-fade-in">
      <div className="flex flex-col space-y-4 mb-8">
        <div className="flex justify-between items-end">
          <div>
            <h2 className="text-3xl font-bold text-slate-900 tracking-tight">Inteligencia de Viajes</h2>
            <p className="text-slate-500 mt-1">
              Análisis crítico de {filteredData.length} destinos.
            </p>
          </div>
        </div>
        
        {/* Filter Bar */}
        <div className="flex flex-col md:flex-row gap-4 p-1">
          {/* Category Chips */}
          <div className="flex flex-wrap gap-2 items-center">
            <span className="text-xs font-bold text-slate-400 uppercase mr-2">Categoría:</span>
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all duration-200 border ${
                  categoryFilter === cat
                    ? 'bg-slate-800 text-white border-slate-800 shadow-md'
                    : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'
                }`}
              >
                {cat === 'All' ? 'Todas' : cat}
              </button>
            ))}
          </div>

          {/* Quality Filter */}
          <div className="flex flex-wrap gap-2 items-center md:ml-8">
             <span className="text-xs font-bold text-slate-400 uppercase mr-2">Calidad:</span>
             {[0, 3, 4, 5].map((score) => (
                <button
                  key={score}
                  onClick={() => setMinScoreFilter(score)}
                  className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all duration-200 border ${
                    minScoreFilter === score
                      ? 'bg-emerald-600 text-white border-emerald-600 shadow-md'
                      : 'bg-white text-slate-600 border-slate-200 hover:border-emerald-200 hover:text-emerald-700'
                  }`}
                >
                  {score === 0 ? 'Todas' : `${score}+ Estrellas`}
                </button>
             ))}
          </div>
        </div>
      </div>

      {/* Grid Layout */}
      {filteredData.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredData.map((item) => (
            <TravelCard key={item.id} item={item} />
          ))}
        </div>
      ) : (
        <div className="text-center py-20 bg-white rounded-2xl border border-dashed border-slate-300">
           <div className="inline-block p-4 rounded-full bg-slate-50 mb-3">
             <span className="text-4xl">🔍</span>
           </div>
           <p className="text-slate-900 font-medium">No se encontraron resultados.</p>
           <p className="text-slate-500 text-sm">Intenta ajustar los filtros de categoría o puntuación.</p>
        </div>
      )}
    </div>
  );
};

export default HistoryDashboard;
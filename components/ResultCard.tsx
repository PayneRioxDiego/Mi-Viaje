import React, { useState } from 'react';
import { TravelAnalysis } from '../types';

interface ResultCardProps {
  data: TravelAnalysis;
}

const ResultCard: React.FC<ResultCardProps> = ({ data }) => {
  const getCategoryColor = (cat: string) => {
    switch (cat.toLowerCase()) {
      case 'lugar': return 'bg-blue-100 text-blue-800';
      case 'comida': return 'bg-orange-100 text-orange-800';
      case 'actividad': return 'bg-green-100 text-green-800';
      case 'consejo': return 'bg-purple-100 text-purple-800';
      default: return 'bg-slate-100 text-slate-800';
    }
  };

  const mapLinks = data.groundingLinks?.filter(l => l.source === 'map') || [];
  const searchLinks = data.groundingLinks?.filter(l => l.source === 'search') || [];

  return (
    <div className="w-full max-w-2xl mx-auto bg-white rounded-xl shadow-lg overflow-hidden border border-slate-100 transform transition-all duration-500 hover:shadow-xl">
      <div className="bg-gradient-to-r from-primary-600 to-fuchsia-600 px-6 py-4">
        <div className="flex justify-between items-center">
          <h2 className="text-xl font-bold text-white">Resultado del Análisis</h2>
          <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${getCategoryColor(data.category)} bg-white/90`}>
            {data.category}
          </span>
        </div>
      </div>
      
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-1">
            <p className="text-sm text-slate-500 font-medium uppercase tracking-wide">Nombre del Lugar</p>
            <p className="text-lg font-semibold text-slate-900">{data.placeName}</p>
          </div>
          
          <div className="space-y-1">
            <p className="text-sm text-slate-500 font-medium uppercase tracking-wide">Ubicación Estimada</p>
            <div className="flex items-center text-slate-900">
              <svg className="w-4 h-4 mr-1 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
              </svg>
              <span className="text-lg font-medium">{data.estimatedLocation}</span>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-1">
            <p className="text-sm text-slate-500 font-medium uppercase tracking-wide">Rango de Precios</p>
            <div className="flex items-center">
               <span className="text-lg font-medium text-emerald-600 bg-emerald-50 px-3 py-1 rounded-md border border-emerald-100">
                 {data.priceRange}
               </span>
            </div>
          </div>

          <div className="space-y-1">
            <p className="text-sm text-slate-500 font-medium uppercase tracking-wide">Veredicto IA</p>
            <div className="flex items-center">
               <span className="text-lg font-medium text-primary-700 bg-primary-50 px-3 py-1 rounded-md border border-primary-100">
                 {data.criticalVerdict}
               </span>
            </div>
          </div>
        </div>

        {/* Grounding / Links Section */}
        {(mapLinks.length > 0 || searchLinks.length > 0) && (
          <div className="pt-4 border-t border-slate-100">
            <p className="text-sm text-slate-500 font-medium uppercase tracking-wide mb-3">Explorar Más</p>
            <div className="flex flex-wrap gap-2">
              {mapLinks.map((link, i) => (
                <a 
                  key={`map-${i}`} 
                  href={link.url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-red-50 text-red-700 border border-red-100 hover:bg-red-100 transition-colors"
                >
                  <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
                  </svg>
                  {link.title}
                </a>
              ))}
              {searchLinks.map((link, i) => (
                <a 
                  key={`search-${i}`} 
                  href={link.url} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="inline-flex items-center px-3 py-1.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 border border-blue-100 hover:bg-blue-100 transition-colors"
                >
                  <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                  </svg>
                  {link.title}
                </a>
              ))}
            </div>
          </div>
        )}

        <div className="pt-4 border-t border-slate-100">
          <p className="text-sm text-slate-500 font-medium uppercase tracking-wide mb-2">Resumen</p>
          <p className="text-slate-700 leading-relaxed italic">
            "{data.summary}"
          </p>
        </div>
      </div>
    </div>
  );
};

export default ResultCard;
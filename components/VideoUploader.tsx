import React, { useState, useCallback } from 'react';
import { AnalysisStatus } from '../types';

interface VideoUploaderProps {
  onAnalyze: (source: File | string) => void;
  status: AnalysisStatus;
}

const VideoUploader: React.FC<VideoUploaderProps> = ({ onAnalyze, status }) => {
  const [url, setUrl] = useState('');
  const [activeTab, setActiveTab] = useState<'url' | 'file'>('url');

  const handleUrlSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (url.trim()) {
      onAnalyze(url);
    }
  };

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.type.startsWith('video/')) {
        onAnalyze(file);
      } else {
        alert("Por favor sube un archivo de video válido.");
      }
    }
  }, [onAnalyze]);

  const isLoading = status === AnalysisStatus.PROCESSING;

  return (
    <div className="w-full max-w-2xl mx-auto mb-10">
      <div className="bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
        {/* Tabs */}
        <div className="flex border-b border-slate-100">
          <button
            onClick={() => setActiveTab('url')}
            className={`flex-1 py-4 text-sm font-semibold transition-colors ${
              activeTab === 'url' 
                ? 'bg-white text-primary-600 border-b-2 border-primary-600' 
                : 'bg-slate-50 text-slate-500 hover:text-slate-700'
            }`}
          >
            Pegar URL
          </button>
          <button
            onClick={() => setActiveTab('file')}
            className={`flex-1 py-4 text-sm font-semibold transition-colors ${
              activeTab === 'file' 
                ? 'bg-white text-primary-600 border-b-2 border-primary-600' 
                : 'bg-slate-50 text-slate-500 hover:text-slate-700'
            }`}
          >
            Subir Archivo
          </button>
        </div>

        <div className="p-8">
          {activeTab === 'url' ? (
            <form onSubmit={handleUrlSubmit} className="space-y-4">
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <svg className="h-5 w-5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                  </svg>
                </div>
                <input
                  type="text"
                  className="block w-full pl-10 pr-3 py-4 border border-slate-300 rounded-lg leading-5 bg-slate-50 placeholder-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-primary-500 focus:border-primary-500 transition-all shadow-sm"
                  placeholder="Pega aquí la URL de TikTok o video..."
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  disabled={isLoading}
                  required
                />
              </div>
              <button
                type="submit"
                disabled={isLoading || !url}
                className="w-full flex justify-center py-4 px-4 border border-transparent rounded-lg shadow-sm text-sm font-bold text-white bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-700 hover:to-primary-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all transform active:scale-[0.98]"
              >
                {isLoading ? (
                  <span className="flex items-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Procesando Video...
                  </span>
                ) : (
                  "Analizar Viaje"
                )}
              </button>
            </form>
          ) : (
            <div className="flex flex-col items-center justify-center border-2 border-dashed border-slate-300 rounded-lg p-10 hover:bg-slate-50 transition-colors relative">
              <input
                type="file"
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                onChange={handleFileChange}
                accept="video/*"
                disabled={isLoading}
              />
              <svg className="w-12 h-12 text-slate-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
              <p className="text-slate-600 font-medium">Haz clic para subir archivo de video</p>
              <p className="text-slate-400 text-sm mt-1">MP4, MOV o WebM</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default VideoUploader;
export interface GroundingLink {
  title: string;
  url: string;
  source: 'map' | 'search';
}

export interface TravelAnalysis {
  category: 'Lugar' | 'Comida' | 'Actividad' | 'Consejo' | 'Otro';
  placeName: string;
  estimatedLocation: string;
  priceRange: string;
  summary: string;
  
  // Critical Intelligence Fields
  score: number; // 1-5
  confidenceLevel: 'Alto' | 'Medio' | 'Bajo';
  criticalVerdict: string; // The "Why" behind the score
  isTouristTrap: boolean;
  
  groundingLinks?: GroundingLink[];
}

export interface AnalysisHistoryItem extends TravelAnalysis {
  id: string;
  timestamp: number;
  fileName: string;
}

export enum AnalysisStatus {
  IDLE = 'IDLE',
  PROCESSING = 'PROCESSING',
  SUCCESS = 'SUCCESS',
  ERROR = 'ERROR',
}
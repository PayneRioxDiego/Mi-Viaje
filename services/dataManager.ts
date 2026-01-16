import { AnalysisHistoryItem } from '../types';
import { API_BASE_URL } from './geminiService';

/**
 * SheetManager (Real Cloud Implementation)
 * Connects to the Python Backend which talks to Google Sheets.
 */
export class SheetManager {
  
  /**
   * Loads data from the backend (Google Sheets)
   */
  static async loadData(): Promise<AnalysisHistoryItem[]> {
    const targetUrl = `${API_BASE_URL}/api/history`;
    console.log(`[SheetManager] Fetching history from ${targetUrl}...`);
    
    try {
      const response = await fetch(targetUrl);
      if (!response.ok) {
        throw new Error(`Server returned ${response.status} ${response.statusText}`);
      }
      
      const data = await response.json();
      
      // Data might come from Sheets as array of arrays or raw dicts depending on implementation
      // For now, assume backend returns clean list of dicts or maps rows correctly
      // We perform a basic mapping if the data looks like raw rows (arrays)
      if (Array.isArray(data) && data.length > 0 && Array.isArray(data[0])) {
         // This handles raw sheets rows if backend returns them raw
         // Assuming order: id, timestamp, placeName, category, score, estimatedLocation, summary, fileName
         return data.slice(1).map((row: any) => ({ // slice(1) to skip header
            id: row[0],
            timestamp: row[1],
            placeName: row[2],
            category: row[3],
            score: Number(row[4]),
            estimatedLocation: row[5],
            summary: row[6],
            fileName: row[7],
            // Defaults for missing fields in raw simple sheet
            confidenceLevel: 'Medio',
            criticalVerdict: row[6],
            isTouristTrap: false 
         })) as AnalysisHistoryItem[];
      }

      return data as AnalysisHistoryItem[];
    } catch (e) {
      console.error(`[SheetManager] Failed to load cloud data from ${targetUrl}. Using local cache.`, e);
      // Fallback to local storage if offline
      const stored = localStorage.getItem('local_backup_db');
      return stored ? JSON.parse(stored) : [];
    }
  }

  /**
   * Saves a new record to the backend
   */
  static async saveRecord(record: AnalysisHistoryItem): Promise<AnalysisHistoryItem[]> {
    console.log(`[SheetManager] Saving to cloud...`, record);

    // Optimistic Update: Save to local backup immediately
    const currentLocal = JSON.parse(localStorage.getItem('local_backup_db') || '[]');
    localStorage.setItem('local_backup_db', JSON.stringify([record, ...currentLocal]));

    try {
      await fetch(`${API_BASE_URL}/api/history`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(record)
      });
      
      // Fetch fresh data to ensure sync
      return await SheetManager.loadData();
    } catch (e) {
      console.error("[SheetManager] Sync failed, saved locally only.", e);
      return [record, ...currentLocal];
    }
  }

  static async clearMockDB() {
    localStorage.removeItem('local_backup_db');
  }
}

export const DataManager = {
    loadDB: SheetManager.loadData,
    saveRecord: SheetManager.saveRecord
};
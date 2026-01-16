import { AnalysisHistoryItem } from '../types';

// Placeholder for Google Service Account Config
const GOOGLE_SHEET_ID = "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"; // Example Placeholder
const CREDENTIALS_PATH = "/path/to/service-account.json"; // Placeholder for backend

/**
 * SheetManager
 * Refactored to act as a Cloud Client for Google Sheets.
 * Replaces local CSV/Pandas logic.
 */
export class SheetManager {
  
  /**
   * Simulates: cargar_datos()
   * Reads all rows from the Google Sheet and converts them to the App's data structure.
   */
  static async loadData(): Promise<AnalysisHistoryItem[]> {
    console.log(`[SheetManager] Connecting to Sheet ${GOOGLE_SHEET_ID} via credentials at ${CREDENTIALS_PATH}...`);
    
    // SIMULATION: In a real app, this would be: await fetch('https://api.backend.com/sheets/read');
    await new Promise(resolve => setTimeout(resolve, 800)); // Simulate Network Latency

    try {
      // For this demo to work without a real Python backend, we mock the cloud data using LocalStorage
      // In production, this line is replaced by the API response parsing.
      const stored = localStorage.getItem('google_sheet_mock_db');
      return stored ? JSON.parse(stored) : [];
    } catch (e) {
      console.error("[SheetManager] Failed to load data from cloud", e);
      return [];
    }
  }

  /**
   * Simulates: guardar_registro(data)
   * Appends a new row to the Google Sheet using worksheet.append_row() logic.
   */
  static async saveRecord(record: AnalysisHistoryItem): Promise<AnalysisHistoryItem[]> {
    console.log(`[SheetManager] Appending row to Sheet...`, record);

    // SIMULATION: In a real app: await fetch('https://api.backend.com/sheets/append', { method: 'POST', body: ... });
    await new Promise(resolve => setTimeout(resolve, 600)); // Simulate Network Latency

    // Mocking the write operation
    const currentData = await SheetManager.loadData();
    const newData = [record, ...currentData];
    localStorage.setItem('google_sheet_mock_db', JSON.stringify(newData));
    
    return newData;
  }

  /**
   * Utility to clear local mock (for testing)
   */
  static async clearMockDB() {
    localStorage.removeItem('google_sheet_mock_db');
  }
}

// Export for backward compatibility if needed, though App.tsx should use SheetManager
export const DataManager = {
    loadDB: SheetManager.loadData,
    saveRecord: SheetManager.saveRecord
};
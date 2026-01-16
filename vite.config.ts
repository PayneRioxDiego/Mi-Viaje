import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Cargar variables de entorno
  const env = loadEnv(mode, (process as any).cwd(), '');

  return {
    plugins: [react()],
    define: {
      // Esto permite usar process.env.API_KEY en el código del navegador
      'process.env.API_KEY': JSON.stringify(env.VITE_GOOGLE_API_KEY),
      'process.env.VITE_API_URL': JSON.stringify(env.VITE_API_URL),
    },
    server: {
      port: 3000,
    },
    build: {
      outDir: 'dist',
    }
  };
});
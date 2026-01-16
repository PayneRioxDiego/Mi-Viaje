import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Cargar variables de entorno
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [react()],
    define: {
      // Usamos JSON.stringify para asegurar que sean strings válidos
      // Si la variable no existe, usamos cadena vacía para evitar crash en build
      'process.env.API_KEY': JSON.stringify(env.API_KEY || env.VITE_GOOGLE_API_KEY || ''),
      'process.env.VITE_API_URL': JSON.stringify(env.VITE_API_URL || ''),
    },
    server: {
      port: 3000,
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true
    }
  };
});
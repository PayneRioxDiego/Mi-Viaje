import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // Cargar variables de entorno del sistema o archivo .env
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [react()],
    define: {
      // Inyectamos las variables de forma segura. 
      // Si no existen durante el build (Docker), quedan vacías para evitar errores de compilación.
      'process.env.API_KEY': JSON.stringify(env.API_KEY || env.VITE_GOOGLE_API_KEY || ''),
      'process.env.VITE_API_URL': JSON.stringify(env.VITE_API_URL || ''),
    },
    server: {
      port: 3000,
      proxy: {
        // Redirige llamadas API al backend local durante desarrollo
        '/analyze': 'http://localhost:5000',
        '/api': 'http://localhost:5000'
      }
    },
    build: {
      outDir: 'dist',
      emptyOutDir: true,
      sourcemap: false
    }
  };
});
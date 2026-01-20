/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "./*.{js,ts,jsx,tsx}"  // <--- ¡ESTA ES LA LÍNEA CLAVE! (Busca en la raíz)
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}

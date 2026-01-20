/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "./*.{js,ts,jsx,tsx}"  // <--- ¡ESTA LÍNEA ES LA QUE TE FALTA!
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}

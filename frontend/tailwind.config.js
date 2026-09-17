/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Vazirmatn", "IRANSans", "Segoe UI", "system-ui", "sans-serif"],
      },
      colors: {
        ink: { 50: "#f6f7f9", 100: "#eceef2", 200: "#d5dae3", 400: "#8c95a8", 600: "#4a5468", 800: "#232a38", 900: "#151a24" },
        brand: { 50: "#eef4ff", 100: "#dbe6ff", 300: "#93b0ff", 500: "#3f63d9", 600: "#2f4cb8", 700: "#253d95" },
        ok: { 100: "#dcf5e6", 600: "#1c8c4e" },
        warn: { 100: "#fdf1d6", 600: "#a9761a" },
        bad: { 100: "#fddede", 600: "#b23b3b" },
      },
    },
  },
  plugins: [],
};

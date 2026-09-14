/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // Persian-friendly system stack (no webfont dependency in Phase 0).
        sans: ["Tahoma", "Vazirmatn", "system-ui", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Vazirmatn", "Tahoma", "sans-serif"] },
      colors: {
        ink: { DEFAULT: "#0f172a", soft: "#475569", mute: "#94a3b8" },
        surface: { DEFAULT: "#ffffff", alt: "#f8fafc", line: "#e2e8f0" },
        brand: { 50:"#eef2ff",100:"#e0e7ff",200:"#c7d2fe",400:"#818cf8",500:"#6366f1",600:"#4f46e5",700:"#4338ca" },
      },
      boxShadow: { card: "0 1px 2px rgba(15,23,42,.04), 0 8px 24px -12px rgba(15,23,42,.12)" },
      keyframes: {
        rise: { "0%": { opacity: "0", transform: "translateY(8px)" }, "100%": { opacity: "1", transform: "none" } },
        pop: { "0%": { transform: "scale(.94)", opacity: "0" }, "100%": { transform: "scale(1)", opacity: "1" } },
        coin: { "0%": { transform: "translateY(0) scale(1)" }, "50%": { transform: "translateY(-10px) scale(1.15)" }, "100%": { transform: "translateY(0) scale(1)" } },
      },
      animation: { rise: "rise .28s ease-out both", pop: "pop .2s ease-out both", coin: "coin .6s ease-in-out" },
    },
  },
  plugins: [],
}

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Vazirmatn', 'Tahoma', 'sans-serif'],
      },
      colors: {
        brand: {
          50: '#eef7ff', 100: '#d9edff', 200: '#bce0ff', 300: '#8ecdff',
          400: '#59b1ff', 500: '#3392fb', 600: '#1d74ef', 700: '#155dd8',
          800: '#184cae', 900: '#1a4388', 950: '#132b57',
        },
      },
      boxShadow: {
        card: '0 1px 3px rgba(16,42,82,.08), 0 8px 24px rgba(16,42,82,.06)',
      },
    },
  },
  plugins: [],
}

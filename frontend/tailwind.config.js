/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          900: "#0b1020",
          800: "#0f152b",
          700: "#161d3a",
          600: "#1d2547",
          500: "#2a3360",
        },
        accent: {
          500: "#7c5cff",
          400: "#9b86ff",
          300: "#beb0ff",
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'monospace'],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(124,92,255,.35), 0 12px 40px -10px rgba(124,92,255,.45)",
      },
    },
  },
  plugins: [],
};

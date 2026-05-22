/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ll: {
          red: "rgb(var(--ll-red) / <alpha-value>)",
          indigo: "rgb(var(--ll-indigo) / <alpha-value>)",
          "indigo-deep": "rgb(var(--ll-indigo-deep) / <alpha-value>)",
          cyan: "rgb(var(--ll-cyan) / <alpha-value>)",
          blue: "rgb(var(--ll-blue) / <alpha-value>)",
          cream: "rgb(var(--ll-cream) / <alpha-value>)",
          ink: "rgb(var(--ll-ink) / <alpha-value>)",
        },
      },
      fontFamily: {
        display: ['"Bebas Neue"', "Oswald", "Impact", "sans-serif"],
        body: ["Inter", '"Helvetica Neue"', "Arial", "sans-serif"],
      },
      borderRadius: {
        DEFAULT: "0",
      },
    },
  },
  plugins: [],
};

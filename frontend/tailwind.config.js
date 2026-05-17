/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ll: {
          red: "#b80028",
          indigo: "#1b1464",
          "indigo-deep": "#0d0840",
          cyan: "#d9fff9",
          blue: "#1371c3",
          cream: "#ffebe7",
          ink: "#262626",
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

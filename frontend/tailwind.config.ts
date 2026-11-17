import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        leaf: { 50: "#f0fdf4", 100: "#dcfce7", 500: "#22c55e", 600: "#16a34a", 700: "#15803d", 900: "#14532d" },
        soil: { 50: "#fafaf9", 100: "#f5f5f4", 400: "#a8a29e", 500: "#78716c", 700: "#44403c", 900: "#1c1917" },
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "'SF Pro Display'", "'Segoe UI'", "Roboto",
          "'Noto Sans'", "'Noto Sans Kannada'", "'Noto Sans Devanagari'", "sans-serif"],
      },
      keyframes: {
        rise: { from: { opacity: "0", transform: "translateY(28px)" }, to: { opacity: "1", transform: "none" } },
        fade: { from: { opacity: "0" }, to: { opacity: "1" } },
      },
      animation: { rise: "rise .9s cubic-bezier(.2,.7,.2,1) both", fade: "fade .6s ease both" },
    },
  },
  plugins: [],
} satisfies Config;

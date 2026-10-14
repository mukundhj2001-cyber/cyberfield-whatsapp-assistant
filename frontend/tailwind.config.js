export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {
    colors: { gold: { 300: "#FFE9A0", 400: "#F5D76E", 500: "#D4AF37", 600: "#C9A227", 700: "#9C7C1C" }, ink: { 900: "#07070A", 800: "#0E0E13", 700: "#16161D", 600: "#22222B", 500: "#2E2E39" } },
    fontFamily: { sans: ["Inter", "Segoe UI", "system-ui", "sans-serif"], display: ["Orbitron", "Inter", "sans-serif"] },
  } },
  plugins: [],
};

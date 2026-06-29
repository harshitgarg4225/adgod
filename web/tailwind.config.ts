import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#0B7A4B", dark: "#075c39", light: "#E6F4EE" },
        hot: "#E11D48",
        warm: "#F59E0B",
        cold: "#64748B",
      },
    },
  },
  plugins: [],
};

export default config;

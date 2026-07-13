import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  root: "src/renderer",
  base: "./",
  css: {
    postcss: {}
  },
  build: {
    outDir: "../../dist/renderer",
    emptyOutDir: true
  },
  server: {
    port: 5173,
    strictPort: true
  }
});

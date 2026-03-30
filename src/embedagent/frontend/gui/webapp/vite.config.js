import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  base: "/static/",
  plugins: [react()],
  build: {
    target: "chrome109",
    outDir: path.resolve(__dirname, "../static"),
    emptyOutDir: true,
  },
});

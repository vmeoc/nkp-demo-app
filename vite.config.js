import { defineConfig } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  plugins: [viteSingleFile()],
  build: {
    rollupOptions: {
      input: { "contract-form": "mcp/contract-form.html" },
    },
    outDir: "mcp-dist",
    emptyOutDir: true,
  },
});

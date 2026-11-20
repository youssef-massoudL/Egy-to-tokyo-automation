import { copyFileSync } from "node:fs";
import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

/** GitHub Pages serves 404.html for unknown paths, so a copy of the app opens deep links. */
function spaFallback(): Plugin {
  return {
    name: "spa-fallback",
    apply: "build",
    closeBundle() {
      const dist = resolve(import.meta.dirname, "dist");
      copyFileSync(resolve(dist, "index.html"), resolve(dist, "404.html"));
    },
  };
}

export default defineConfig({
  // The folder the site is served from. On the Kanz Market Close site it is the "team" tab:
  // SITE_BASE=/Egy-to-tokyo-automation/team/ (set by that repo's Deploy website workflow).
  base: process.env.SITE_BASE || "/kanz-team/",
  plugins: [react(), spaFallback()],
  server: {
    port: 5173,
  },
});

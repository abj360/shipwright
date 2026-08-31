/**
 * vite.config.ts --- dev server and build settings for the live view
 *
 * Contains:
 *   default: vite configuration with the react plugin and gateway proxy
 */

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const GATEWAY_TARGET = process.env.GATEWAY_URL ?? "http://localhost:4000";
const GATEWAY_TOKEN = process.env.GATEWAY_TOKEN ?? "dev-token";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // The token is attached here, not in the bundle: anything the browser
      // holds is readable by anyone who opens devtools.
      "/runs": {
        target: GATEWAY_TARGET,
        ws: true,
        headers: { Authorization: `Bearer ${GATEWAY_TOKEN}` },
      },
    },
  },
});

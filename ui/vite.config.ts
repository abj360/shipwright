#!/usr/bin/env ts-node
/**
 * vite.config.ts --- dev server and build settings for the live view
 *
 * Contains:
 *   default: vite configuration with the react plugin and gateway proxy
 */

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/runs": "http://localhost:4000",
    },
  },
});

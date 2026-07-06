#!/usr/bin/env ts-node
/**
 * main.tsx --- browser entrypoint mounting the shipwright live view
 */

import { App } from "./App";
import React from "react";
import { createRoot } from "react-dom/client";

const host = document.getElementById("root");
if (host !== null) {
  createRoot(host).render(<App />);
}

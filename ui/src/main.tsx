/**
 * main.tsx --- browser entrypoint mounting the shipwright live view
 */

import { App } from "./App";
import { createRoot } from "react-dom/client";

const host = document.getElementById("root");
if (host === null) {
  throw new Error("missing #root element; index.html and main.tsx disagree");
}
createRoot(host).render(<App />);

#!/usr/bin/env ts-node
/**
 * theme.ts --- color tokens and xterm theme for the live view
 *
 * Contains:
 *   Theme: color tokens
 *   darkTheme: default palette
 *   xtermTheme: xterm.js theme
 */

export interface Theme {
  background: string;
  foreground: string;
  accent: string;
  add: string;
  del: string;
  hunk: string;
}

export const darkTheme: Theme = {
  background: "#0d1117",
  foreground: "#c9d1d9",
  accent: "#58a6ff",
  add: "#3fb950",
  del: "#f85149",
  hunk: "#8b949e",
};

export const xtermTheme = {
  background: darkTheme.background,
  foreground: darkTheme.foreground,
  cursor: darkTheme.accent,
};

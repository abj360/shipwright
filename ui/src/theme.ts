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
  add: "#2ea043",
  del: "#f85149",
  hunk: "#8b949e",
};

export const xtermTheme = {
  background: darkTheme.background,
  foreground: darkTheme.foreground,
  cursor: darkTheme.accent,
  black: "#484f58",
  red: darkTheme.del,
  green: darkTheme.add,
  yellow: "#d29922",
  blue: darkTheme.accent,
  magenta: "#bc8cff",
  cyan: "#39c5cf",
  white: darkTheme.foreground,
};

export const linkColor = "#58a6ff";

export const focusRing = "#1f6feb";

export const badgeOkBg = "#1a7f3733";

export const ansiBrightGreen = "#56d364";

export const panelBorder = "#21262d";

export const cursorAlt = "#c9d1d9";

export const scrollTrack = "#0d1117";

export const ansiBrightMagenta = "#d2a8ff";

export const borderSubtle = "#30363d";

export const panelBg = "#161b22";

export const badgeWarnBg = "#9a670033";

export const badgeErrBg = "#d1242f33";

export const ansiBrightBlack = "#6e7681";

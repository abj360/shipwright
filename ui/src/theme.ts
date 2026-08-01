#!/usr/bin/env ts-node
/**
 * theme.ts --- color tokens and xterm theme for the live view
 *
 * Contains:
 *   Theme: color tokens
 *   darkTheme: default palette
 *   xtermTheme: xterm.js theme
 *   fonts: UI and monospace font stacks
 */

export interface Theme {
  background: string;
  foreground: string;
  accent: string;
  add: string;
  del: string;
  hunk: string;
  statusOk: string;
  statusErr: string;
  statusWarn: string;
}

export const darkTheme: Theme = {
  background: "#0d1117",
  foreground: "#c9d1d9",
  accent: "#6cb6ff",
  add: "#2ea043",
  del: "#f85149",
  hunk: "#8b949e",
  statusOk: "#3fb950",
  statusErr: "#f85149",
  statusWarn: "#d29922",
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

export const ansiBrightBlue = "#79c0ff";

export const ansiBrightWhite = "#f0f6fc";

export const ansiBrightCyan = "#56d4dd";

export const ansiBrightRed = "#ff7b72";

export const selectionBg = "#264f78";

export const ansiBrightYellow = "#e3b341";

export const scrollThumb = "#30363d";

export const fonts = {
  ui: "-apple-system, 'Segoe UI', sans-serif",
  mono: "'JetBrains Mono', ui-monospace, monospace",
} as const;

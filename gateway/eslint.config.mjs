/**
 * eslint.config.mjs --- lint rules for the gateway sources and tests
 *
 * Contains:
 *   default: flat config pairing the recommended JS and TypeScript rules
 */

import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/**", "node_modules/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "@typescript-eslint/no-non-null-assertion": "warn",
    },
  },
);

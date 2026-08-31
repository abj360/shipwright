/**
 * vitest.config.ts --- test runner settings for the gateway suite
 *
 * Contains:
 *   default: vitest configuration pointing at tests/ with a test environment
 */

import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.test.ts"],
    env: {
      GITHUB_TOKEN: "test-token",
      REPO_URL: "https://github.com/org/repo",
    },
  },
});

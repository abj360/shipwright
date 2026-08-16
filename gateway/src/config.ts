#!/usr/bin/env ts-node
/**
 * config.ts --- environment parsing and typed gateway configuration
 *
 * Contains:
 *   GatewayConfig: typed gateway configuration
 *   loadConfig(): parses env into typed config, failing fast
 */

import { z } from "zod";

const envSchema = z.object({
  PORT: z.coerce.number().int().positive().default(4000),
  GITHUB_TOKEN: z.string().min(1),
  WEBHOOK_SECRET: z.string().min(1).default("dev-secret"),
  REPO_URL: z.string().url(),
  WORK_DIR: z.string().default("/tmp/shipwright-work"),
  AGENT_URL: z.string().url().default("http://agent:8000"),
  GATEWAY_TOKEN: z.string().min(1).default("dev-token"),
});

export type GatewayConfig = z.infer<typeof envSchema>;

export function loadConfig(env: NodeJS.ProcessEnv = process.env): GatewayConfig {
  /**
   * Parses process environment into a typed config, failing fast on bad input.
   *
   * @param env - Environment to parse; defaults to process.env.
   * @returns config - Typed gateway configuration.
   */
  const parsed = envSchema.safeParse(env);
  if (!parsed.success) {
    throw new Error(`invalid gateway configuration: ${parsed.error.message}`);
  }
  return parsed.data;
}

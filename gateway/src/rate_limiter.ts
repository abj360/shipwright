#!/usr/bin/env ts-node
/**
 * rate_limiter.ts --- request queue with Retry-After-aware backoff for the GitHub API
 *
 * Contains:
 *   parseRetryAfter(): extracts the Retry-After hint
 *   isRateLimitError(): classifies rate-limit responses
 *   backoffMs(): exponential backoff with jitter
 *   RequestQueue: serializes mutations with polite backoff
 */

import pino from "pino";

const logger = pino.default({ name: "rate-limiter" });
const DEFAULT_MIN_INTERVAL_MS = 1_000;
const DEFAULT_MAX_ATTEMPTS = 7;
const JITTER_MS = 500;

export function parseRetryAfter(headers: Record<string, string>): number | null {
  /**
   * Extracts the Retry-After hint GitHub sends on secondary rate limits.
   *
   * @param headers - Response headers from a failed request.
   * @returns waitMs - Milliseconds to wait, or null when absent.
   */
  const value = headers["retry-after"];
  if (value === undefined) {
    return null;
  }
  const seconds = Number(value);
  return Number.isFinite(seconds) ? seconds * 1000 : null;
}

export function isRateLimitError(error: unknown): boolean {
  /**
   * Decides whether an error is a GitHub rate-limit response.
   *
   * @param error - Thrown error to classify.
   * @returns isRateLimit - True for 429 and 403-with-retry-after responses.
   */
  const status = (error as { status?: number }).status;
  return status === 429 || status === 403;
}

export function backoffMs(attempt: number): number {
  /**
   * Computes exponential backoff with jitter.
   *
   * @param attempt - Zero-based retry attempt.
   * @returns waitMs - Milliseconds to wait before the next attempt.
   */
  return 1_000 * 2 ** attempt + Math.floor(Math.random() * JITTER_MS);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export class RequestQueue {
  /**
   * Serializes GitHub mutations and retries rate-limited ones politely.
   */

  private chain: Promise<unknown> = Promise.resolve();
  private readonly minIntervalMs: number;
  private readonly maxAttempts: number;
  private lastStartedAt = 0;

  constructor(options: { minIntervalMs?: number; maxAttempts?: number } = {}) {
    this.minIntervalMs = options.minIntervalMs ?? DEFAULT_MIN_INTERVAL_MS;
    this.maxAttempts = options.maxAttempts ?? DEFAULT_MAX_ATTEMPTS;
  }

  async enqueue<T>(operation: () => Promise<T>): Promise<T> {
    /**
     * Queues one operation behind prior ones and runs it with backoff.
     *
     * @param operation - API call to run.
     * @returns result - Operation result.
     */
    const task = this.chain.then(() => this.runWithBackoff(operation));
    this.chain = task.catch(() => undefined);
    return task;
  }

  private async runWithBackoff<T>(operation: () => Promise<T>): Promise<T> {
    let lastError: unknown;
    for (let attempt = 0; attempt < this.maxAttempts; attempt += 1) {
      await this.throttle();
      try {
        return await operation();
      } catch (error) {
        lastError = error;
        if (!isRateLimitError(error)) {
          throw error;
        }
        const headers = (error as { headers?: Record<string, string> }).headers ?? {};
        const retryAfter = parseRetryAfter(headers);
        logger.warn({ attempt, retryAfter }, "rate limited; backing off");
        await sleep(retryAfter ?? backoffMs(attempt));
      }
    }
    throw lastError;
  }

  private async throttle(): Promise<void> {
    const wait = Math.max(0, this.lastStartedAt + this.minIntervalMs - Date.now());
    if (wait > 0) {
      await sleep(wait);
    }
    this.lastStartedAt = Date.now();
  }
}

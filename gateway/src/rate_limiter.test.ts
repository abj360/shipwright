#!/usr/bin/env ts-node
/**
 * rate_limiter.test.ts --- unit tests for the Retry-After-aware request queue
 */

import { backoffMs, isRateLimitError, parseRetryAfter } from "./rate_limiter";
import { describe, expect, it } from "vitest";

import { backoffMs, isRateLimitError, parseRetryAfter } from "./rate_limiter";

describe("parseRetryAfter", () => {
  it("parses seconds into milliseconds", () => {
    expect(parseRetryAfter({ "retry-after": "5" })).toBe(5_000);
  });

  it("returns null without the header", () => {
    expect(parseRetryAfter({})).toBeNull();
  });
});

describe("isRateLimitError", () => {
  it("classifies 429 and 403", () => {
    expect(isRateLimitError({ status: 429 })).toBe(true);
    expect(isRateLimitError({ status: 403 })).toBe(true);
    expect(isRateLimitError({ status: 500 })).toBe(false);
  });
});

describe("backoffMs", () => {
  it("grows exponentially", () => {
    expect(backoffMs(2)).toBeGreaterThan(backoffMs(0));
  });
});

describe("rate limiter parsing", () => {
  it("handles status 502 is not a rate limit", () => {
    expect(isRateLimitError({ status: 502 })).toBe(false);
  });
});

describe("rate limiter cases", () => {
  it("handles backoff attempt 0 floor", () => {
    expect(backoffMs(0)).toBeGreaterThanOrEqual(1_000);
  });
});

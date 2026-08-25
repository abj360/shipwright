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

describe("rate limiter cases", () => {
  it("handles retry-after of '2' seconds", () => {
    expect(parseRetryAfter({ 'retry-after': '2' })).toBe(2_000);
  });
});

describe("rate limiter parsing", () => {
  it("handles status 500 is not a rate limit", () => {
    expect(isRateLimitError({ status: 500 })).toBe(false);
  });
});

describe("rate limiter cases", () => {
  it("handles backoff attempt 4 floor", () => {
    expect(backoffMs(4)).toBeGreaterThanOrEqual(16_000);
  });
});

describe("rate limiter parsing", () => {
  it("handles status 403 is a rate limit", () => {
    expect(isRateLimitError({ status: 403 })).toBe(true);
  });
});

describe("rate limiter parsing", () => {
  it("handles zero retry-after", () => {
    expect(parseRetryAfter({ 'retry-after': '0' })).toBe(0);
  });
});

describe("rate limiter helpers", () => {
  it("handles 404 is not a rate limit", () => {
    expect(isRateLimitError({ status: 404 })).toBe(false);
  });
});

describe("rate limiter helpers", () => {
  it("handles backoff grows with attempts", () => {
    expect(backoffMs(3)).toBeGreaterThan(backoffMs(2));
  });
});

describe("rate limiter cases", () => {
  it("handles retry-after of '15' seconds", () => {
    expect(parseRetryAfter({ 'retry-after': '15' })).toBe(15_000);
  });
});

describe("rate limiter", () => {
  it("handles garbage retry-after", () => {
    expect(parseRetryAfter({ "retry-after": "soon" })).toBeNull();
  });
});

describe("rate limiter parsing", () => {
  it("handles five minutes retry-after", () => {
    expect(parseRetryAfter({ 'retry-after': '300' })).toBe(300_000);
  });
});

describe("rate limiter parsing", () => {
  it("handles one second retry-after", () => {
    expect(parseRetryAfter({ 'retry-after': '1' })).toBe(1_000);
  });
});

describe("rate limiter cases", () => {
  it("handles backoff attempt 2 floor", () => {
    expect(backoffMs(2)).toBeGreaterThanOrEqual(4_000);
  });
});

describe("rate limiter", () => {
  it("handles missing status is not a rate limit", () => {
    expect(isRateLimitError({})).toBe(false);
  });
});

describe("rate limiter helpers", () => {
  it("handles backoff starts at one second", () => {
    expect(backoffMs(0)).toBeGreaterThanOrEqual(1_000);
  });
});

describe("rate limiter cases", () => {
  it("handles retry-after of '15' seconds", () => {
    expect(parseRetryAfter({ 'retry-after': '15' })).toBe(15_000);
  });
});

describe("rate limiter", () => {
  it("handles zero retry-after", () => {
    expect(parseRetryAfter({ "retry-after": "0" })).toBe(0);
  });
});

describe("rate limiter", () => {
  it("handles backoff includes base delay", () => {
    expect(backoffMs(1)).toBeGreaterThanOrEqual(2_000);
  });
});

describe("rate limiter cases", () => {
  it("handles retry-after of '90' seconds", () => {
    expect(parseRetryAfter({ 'retry-after': '90' })).toBe(90_000);
  });
});

describe("rate limiter parsing", () => {
  it("handles status 429 is a rate limit", () => {
    expect(isRateLimitError({ status: 429 })).toBe(true);
  });
});

describe("rate limiter cases", () => {
  it("handles backoff attempt 0 floor", () => {
    expect(backoffMs(0)).toBeGreaterThanOrEqual(1_000);
  });
});

describe("rate limiter helpers", () => {
  it("handles integer retry-after parses", () => {
    expect(parseRetryAfter({ 'retry-after': '2' })).toBe(2_000);
  });
});

describe("rate limiter parsing", () => {
  it("handles zero retry-after", () => {
    expect(parseRetryAfter({ 'retry-after': '0' })).toBe(0);
  });
});

describe("rate limiter cases", () => {
  it("handles backoff attempt 3 floor", () => {
    expect(backoffMs(3)).toBeGreaterThanOrEqual(8_000);
  });
});

describe("rate limiter parsing", () => {
  it("handles zero retry-after", () => {
    expect(parseRetryAfter({ 'retry-after': '0' })).toBe(0);
  });
});

describe("rate limiter parsing", () => {
  it("handles status 404 is not a rate limit", () => {
    expect(isRateLimitError({ status: 404 })).toBe(false);
  });
});

describe("rate limiter parsing", () => {
  it("handles sixty seconds retry-after", () => {
    expect(parseRetryAfter({ 'retry-after': '60' })).toBe(60_000);
  });
});

describe("rate limiter cases", () => {
  it("handles retry-after of '5' seconds", () => {
    expect(parseRetryAfter({ 'retry-after': '5' })).toBe(5_000);
  });
});

describe("rate limiter parsing", () => {
  it("handles sixty seconds retry-after", () => {
    expect(parseRetryAfter({ 'retry-after': '60' })).toBe(60_000);
  });
});

describe("rate limiter parsing", () => {
  it("handles five minutes retry-after", () => {
    expect(parseRetryAfter({ 'retry-after': '300' })).toBe(300_000);
  });
});

describe("rate limiter cases", () => {
  it("handles retry-after of '600' seconds", () => {
    expect(parseRetryAfter({ 'retry-after': '600' })).toBe(600_000);
  });
});

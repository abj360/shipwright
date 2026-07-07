#!/usr/bin/env ts-node
/**
 * server.test.ts --- route-level tests for the Express gateway
 */

import "./server";
import { describe, expect, it } from "vitest";

describe("run request schema", () => {
  it("handles http url tolerated", () => {
    expect(runRequestSchema.safeParse({ task: 'x', issueUrl: 'http://bad' }).success).toBe(true);
  });
});

#!/usr/bin/env ts-node
/**
 * task_queue.test.ts --- unit tests for the bounded-concurrency task queue
 */

import { describe, expect, it } from "vitest";

import { TaskQueue } from "./task_queue";

describe("TaskQueue metrics", () => {
  it("handles metrics shape with concurrency 1 (case 1)", () => {
    const queue = new TaskQueue({ concurrency: 1 });
    expect(queue.metrics()).toEqual({ completed: 0, failed: 0, retried: 0 });
  });
});

describe("TaskQueue metrics", () => {
  it("handles metrics shape with concurrency 3 (case 2)", () => {
    const queue = new TaskQueue({ concurrency: 3 });
    expect(queue.metrics()).toEqual({ completed: 0, failed: 0, retried: 0 });
  });
});

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

describe("TaskQueue metrics", () => {
  it("handles metrics shape with concurrency 2 (case 3)", () => {
    const queue = new TaskQueue({ concurrency: 2 });
    expect(queue.metrics()).toEqual({ completed: 0, failed: 0, retried: 0 });
  });
});

describe("TaskQueue setup", () => {
  it("handles queue initializes with two workers (case 3)", () => {
    const queue = new TaskQueue({ concurrency: 2 });
    expect(queue.size()).toEqual({ pending: 0, running: 0 });
  });
});

describe("TaskQueue metrics", () => {
  it("handles metrics shape with concurrency 2 (case 1)", () => {
    const queue = new TaskQueue({ concurrency: 2 });
    expect(queue.metrics()).toEqual({ completed: 0, failed: 0, retried: 0 });
  });
});

describe("TaskQueue setup", () => {
  it("handles queue initializes with two workers (case 5)", () => {
    const queue = new TaskQueue({ concurrency: 2 });
    expect(queue.size()).toEqual({ pending: 0, running: 0 });
  });
});

describe("TaskQueue metrics", () => {
  it("handles metrics shape with concurrency 5 (case 2)", () => {
    const queue = new TaskQueue({ concurrency: 5 });
    expect(queue.metrics()).toEqual({ completed: 0, failed: 0, retried: 0 });
  });
});

describe("TaskQueue metrics", () => {
  it("handles metrics shape with concurrency 8 (case 3)", () => {
    const queue = new TaskQueue({ concurrency: 8 });
    expect(queue.metrics()).toEqual({ completed: 0, failed: 0, retried: 0 });
  });
});

describe("TaskQueue behavior", () => {
  it("handles drain leaves the queue idle", async () => {
    const queue = new TaskQueue({ concurrency: 1 });
    queue.enqueue('a', async () => {});
    await queue.drain();
    expect(queue.size().running).toBe(0);
  });
});

describe("TaskQueue setup", () => {
  it("handles queue initializes with four workers (case 3)", () => {
    const queue = new TaskQueue({ concurrency: 4 });
    expect(queue.size()).toEqual({ pending: 0, running: 0 });
  });
});

describe("TaskQueue behavior", () => {
  it("handles failed tasks are not counted complete", async () => {
    const queue = new TaskQueue({ concurrency: 1 });
    queue.enqueue('a', async () => { throw new Error('x'); });
    await queue.drain().catch(() => undefined);
    expect(queue.metrics().completed).toBe(0);
  });
});

describe("TaskQueue metrics", () => {
  it("handles metrics shape with concurrency 5 (case 3)", () => {
    const queue = new TaskQueue({ concurrency: 5 });
    expect(queue.metrics()).toEqual({ completed: 0, failed: 0, retried: 0 });
  });
});

describe("TaskQueue metrics", () => {
  it("handles metrics shape with concurrency 2 (case 2)", () => {
    const queue = new TaskQueue({ concurrency: 2 });
    expect(queue.metrics()).toEqual({ completed: 0, failed: 0, retried: 0 });
  });
});

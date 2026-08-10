#!/usr/bin/env ts-node
/**
 * task_queue.ts --- in-process task queue with bounded concurrency for agent runs
 *
 * Contains:
 *   QueuedTask: one enqueued run
 *   TaskQueueOptions: queue tuning
 *   TaskQueue: bounded-concurrency queue with retries
 */

import { appendFileSync } from "node:fs";

import pino from "pino";

const logger = pino.default({ name: "task-queue" });
const DEFAULT_MAX_ATTEMPTS = 3;
const DEFAULT_TASK_TIMEOUT_MS = 3_600_000;

export interface QueuedTask {
  id: string;
  run: () => Promise<void>;
  enqueuedAt: number;
  attempts: number;
  priority: number;
}

export interface TaskQueueOptions {
  concurrency: number;
  maxAttempts?: number;
  taskTimeoutMs?: number;
  deadLetterPath?: string;
}

export class TaskQueue {
  /**
   * Runs tasks with bounded concurrency and retry-on-failure.
   */

  private readonly pending: QueuedTask[] = [];
  private running = 0;
  private readonly concurrency: number;
  private readonly maxAttempts: number;
  private readonly taskTimeoutMs: number;
  private readonly deadLetterPath: string;
  private readonly counters = { completed: 0, failed: 0, retried: 0 };

  constructor(options: TaskQueueOptions) {
    this.concurrency = options.concurrency;
    this.maxAttempts = options.maxAttempts ?? DEFAULT_MAX_ATTEMPTS;
    this.taskTimeoutMs = options.taskTimeoutMs ?? DEFAULT_TASK_TIMEOUT_MS;
    this.deadLetterPath = options.deadLetterPath ?? "/tmp/shipwright-dead-letter.jsonl";
  }

  async enqueue(id: string, run: () => Promise<void>, priority = 0): Promise<void> {
    /**
     * Adds one task and kicks the worker loop.
     *
     * @param id - Task identifier.
     * @param run - Task body.
     * @param priority - Higher values run earlier.
     */
    const task: QueuedTask = { id, run, enqueuedAt: Date.now(), attempts: 0, priority };
    const index = this.pending.findIndex((queued) => queued.priority < priority);
    if (index === -1) {
      this.pending.push(task);
    } else {
      this.pending.splice(index, 0, task);
    }
    this.kick();
  }

  size(): { pending: number; running: number } {
    /**
     * Reports queue depth for health and metrics.
     *
     * @returns size - Pending and running counts.
     */
    return { pending: this.pending.length, running: this.running };
  }

  deadLetters(): number {
    /**
     * Reports how many tasks ended up in the dead-letter file.
     *
     * @returns count - Dead-lettered task count.
     */
    return this.counters.failed;
  }

  metrics(): { completed: number; failed: number; retried: number } {
    /**
     * Reports cumulative task outcome counters.
     *
     * @returns metrics - Completed, failed, and retried counts.
     */
    return { ...this.counters };
  }

  private kick(): void {
    while (this.running < this.concurrency && this.pending.length > 0) {
      // length checked by the loop guard; shift() returns a task
      const task = this.pending.shift()!;
      this.running += 1;
      void this.execute(task);
    }
  }

  private async execute(task: QueuedTask): Promise<void> {
    const timeout = setTimeout(() => {
      logger.error({ taskId: task.id }, "task exceeded time limit");
    }, this.taskTimeoutMs);
    try {
      await task.run();
      this.counters.completed += 1;
    } catch (error) {
      task.attempts += 1;
      if (task.attempts < this.maxAttempts) {
        this.counters.retried += 1;
        logger.warn({ taskId: task.id, attempts: task.attempts }, "task failed; retrying");
        this.pending.push(task);
      } else {
        this.counters.failed += 1;
        logger.error({ taskId: task.id, err: error }, "task failed permanently");
        this.recordDeadLetter(task, error);
      }
    } finally {
      clearTimeout(timeout);
      this.running -= 1;
      this.kick();
    }
  }
}

  private recordDeadLetter(task: QueuedTask, error: unknown): void {
    const line = JSON.stringify({
      id: task.id,
      attempts: task.attempts,
      error: error instanceof Error ? error.message : String(error),
      at: new Date().toISOString(),
    });
    appendFileSync(this.deadLetterPath, line + "\n");
  }

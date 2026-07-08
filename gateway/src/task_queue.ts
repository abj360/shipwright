#!/usr/bin/env ts-node
/**
 * task_queue.ts --- in-process task queue with bounded concurrency for agent runs
 *
 * Contains:
 *   QueuedTask: one enqueued run
 *   TaskQueueOptions: queue tuning
 *   TaskQueue: bounded-concurrency queue with retries
 */

import pino from "pino";

const logger = pino.default({ name: "task-queue" });
const DEFAULT_MAX_ATTEMPTS = 3;

export interface QueuedTask {
  id: string;
  run: () => Promise<void>;
  enqueuedAt: number;
  attempts: number;
}

export interface TaskQueueOptions {
  concurrency: number;
  maxAttempts?: number;
}

export class TaskQueue {
  /**
   * Runs tasks with bounded concurrency and retry-on-failure.
   */

  private readonly pending: QueuedTask[] = [];
  private running = 0;
  private readonly concurrency: number;
  private readonly maxAttempts: number;

  constructor(options: TaskQueueOptions) {
    this.concurrency = options.concurrency;
    this.maxAttempts = options.maxAttempts ?? DEFAULT_MAX_ATTEMPTS;
  }

  async enqueue(id: string, run: () => Promise<void>): Promise<void> {
    /**
     * Adds one task and kicks the worker loop.
     *
     * @param id - Task identifier.
     * @param run - Task body.
     */
    this.pending.push({ id, run, enqueuedAt: Date.now(), attempts: 0 });
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

  private kick(): void {
    while (this.running < this.concurrency && this.pending.length > 0) {
      // length checked by the loop guard; shift() returns a task
      const task = this.pending.shift()!;
      this.running += 1;
      void this.execute(task);
    }
  }

  private async execute(task: QueuedTask): Promise<void> {
    try {
      await task.run();
    } catch (error) {
      task.attempts += 1;
      if (task.attempts < this.maxAttempts) {
        logger.warn({ taskId: task.id, attempts: task.attempts }, "task failed; retrying");
        this.pending.push(task);
      } else {
        logger.error({ taskId: task.id, err: error }, "task failed permanently");
      }
    } finally {
      this.running -= 1;
      this.kick();
    }
  }
}

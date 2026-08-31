/**
 * run_streams.ts --- per-run output buffers that late subscribers can catch up on
 *
 * Contains:
 *   StreamSubscriber: receives one run's output lines
 *   RunStreams: buffers run output, fans it out, and signals completion
 */

const DEFAULT_BUFFER_LINES = 2_000;

export type StreamSubscriber = (line: string) => void;

interface RunStream {
  lines: string[];
  subscribers: Set<StreamSubscriber>;
  onEnd: Set<() => void>;
  ended: boolean;
}

export class RunStreams {
  /**
   * Buffers each run's output and fans new lines out to live subscribers.
   *
   * A viewer that connects halfway through a run still needs the output it
   * missed, so every line is kept in a bounded buffer and replayed on
   * subscribe rather than only being forwarded live.
   */

  private readonly streams = new Map<string, RunStream>();
  private readonly bufferLines: number;

  constructor(options: { bufferLines?: number } = {}) {
    this.bufferLines = options.bufferLines ?? DEFAULT_BUFFER_LINES;
  }

  append(runId: string, line: string): void {
    /**
     * Records one output line and forwards it to every live subscriber.
     *
     * @param runId - Run the line belongs to.
     * @param line - Output line, without a trailing newline.
     */
    const stream = this.streamFor(runId);
    stream.lines.push(line);
    if (stream.lines.length > this.bufferLines) {
      stream.lines.splice(0, stream.lines.length - this.bufferLines);
    }
    for (const subscriber of stream.subscribers) {
      subscriber(line);
    }
  }

  subscribe(runId: string, subscriber: StreamSubscriber): () => void {
    /**
     * Replays the buffered output to a subscriber, then keeps it up to date.
     *
     * @param runId - Run to follow.
     * @param subscriber - Called once per buffered line, then per new line.
     * @returns unsubscribe - Detaches the subscriber.
     */
    const stream = this.streamFor(runId);
    for (const line of stream.lines) {
      subscriber(line);
    }
    stream.subscribers.add(subscriber);
    return () => {
      stream.subscribers.delete(subscriber);
    };
  }

  end(runId: string): void {
    /**
     * Marks a run's output as complete and detaches its subscribers.
     *
     * @param runId - Run that finished.
     */
    const stream = this.streamFor(runId);
    stream.ended = true;
    for (const subscriber of stream.onEnd) {
      subscriber();
    }
    stream.onEnd.clear();
  }

  onEnd(runId: string, subscriber: () => void): () => void {
    /**
     * Registers a callback for when a run's output completes.
     *
     * @param runId - Run to watch.
     * @param subscriber - Called once, when the run ends.
     * @returns cancel - Detaches the callback.
     */
    const stream = this.streamFor(runId);
    stream.onEnd.add(subscriber);
    return () => {
      stream.onEnd.delete(subscriber);
    };
  }

  hasEnded(runId: string): boolean {
    /**
     * Reports whether a run's output is complete.
     *
     * @param runId - Run to check.
     * @returns ended - True once end() has been called for the run.
     */
    return this.streams.get(runId)?.ended ?? false;
  }

  buffered(runId: string): string[] {
    /**
     * Returns the output buffered for one run.
     *
     * @param runId - Run to read.
     * @returns lines: Buffered output lines, oldest first.
     */
    return [...(this.streams.get(runId)?.lines ?? [])];
  }

  forget(runId: string): void {
    /**
     * Drops a finished run's buffer so long-lived processes stay bounded.
     *
     * @param runId - Run to discard.
     */
    this.streams.delete(runId);
  }

  private streamFor(runId: string): RunStream {
    const existing = this.streams.get(runId);
    if (existing !== undefined) {
      return existing;
    }
    const created: RunStream = {
      lines: [],
      subscribers: new Set(),
      onEnd: new Set(),
      ended: false,
    };
    this.streams.set(runId, created);
    return created;
  }
}

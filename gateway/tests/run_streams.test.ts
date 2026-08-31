/**
 * run_streams.test.ts --- unit tests for the per-run output buffer and fan-out
 */

import { RunStreams } from "../src/run_streams";
import { describe, expect, it, vi } from "vitest";

describe("RunStreams", () => {
  it("forwards new lines to a live subscriber", () => {
    const streams = new RunStreams();
    const seen: string[] = [];
    streams.subscribe("r1", (line) => seen.push(line));
    streams.append("r1", "step 0");
    streams.append("r1", "step 1");
    expect(seen).toEqual(["step 0", "step 1"]);
  });

  it("replays what a late subscriber missed", () => {
    const streams = new RunStreams();
    streams.append("r1", "step 0");
    streams.append("r1", "step 1");
    const seen: string[] = [];
    streams.subscribe("r1", (line) => seen.push(line));
    expect(seen).toEqual(["step 0", "step 1"]);
  });

  it("keeps runs separate", () => {
    const streams = new RunStreams();
    const first: string[] = [];
    streams.subscribe("r1", (line) => first.push(line));
    streams.append("r2", "other run");
    expect(first).toEqual([]);
    expect(streams.buffered("r2")).toEqual(["other run"]);
  });

  it("stops delivering after unsubscribe", () => {
    const streams = new RunStreams();
    const seen: string[] = [];
    const stop = streams.subscribe("r1", (line) => seen.push(line));
    streams.append("r1", "before");
    stop();
    streams.append("r1", "after");
    expect(seen).toEqual(["before"]);
  });

  it("drops the oldest lines once the buffer is full", () => {
    const streams = new RunStreams({ bufferLines: 3 });
    for (const line of ["a", "b", "c", "d", "e"]) {
      streams.append("r1", line);
    }
    expect(streams.buffered("r1")).toEqual(["c", "d", "e"]);
  });

  it("reports a run as ended only after end()", () => {
    const streams = new RunStreams();
    streams.append("r1", "working");
    expect(streams.hasEnded("r1")).toBe(false);
    streams.end("r1");
    expect(streams.hasEnded("r1")).toBe(true);
  });

  it("treats an unknown run as neither ended nor buffered", () => {
    const streams = new RunStreams();
    expect(streams.hasEnded("nope")).toBe(false);
    expect(streams.buffered("nope")).toEqual([]);
  });

  it("forgets a run's buffer on request", () => {
    const streams = new RunStreams();
    streams.append("r1", "a");
    streams.forget("r1");
    expect(streams.buffered("r1")).toEqual([]);
  });

  it("fans one line out to every subscriber", () => {
    const streams = new RunStreams();
    const first = vi.fn();
    const second = vi.fn();
    streams.subscribe("r1", first);
    streams.subscribe("r1", second);
    streams.append("r1", "shared");
    expect(first).toHaveBeenCalledWith("shared");
    expect(second).toHaveBeenCalledWith("shared");
  });

  it("notifies end subscribers exactly once", () => {
    const streams = new RunStreams();
    const done = vi.fn();
    streams.onEnd("r1", done);
    streams.end("r1");
    streams.end("r1");
    expect(done).toHaveBeenCalledTimes(1);
  });

  it("stops notifying an end subscriber that cancelled", () => {
    const streams = new RunStreams();
    const done = vi.fn();
    const cancel = streams.onEnd("r1", done);
    cancel();
    streams.end("r1");
    expect(done).not.toHaveBeenCalled();
  });

  it("keeps the buffer readable after the run ends", () => {
    const streams = new RunStreams();
    streams.append("r1", "step 0");
    streams.end("r1");
    expect(streams.buffered("r1")).toEqual(["step 0"]);
  });
});

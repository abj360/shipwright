#!/usr/bin/env ts-node
/**
 * webhooks.ts --- GitHub webhook receiver turning issue events into agent runs
 *
 * Contains:
 *   verifySignature(): verifies the delivery HMAC
 *   createWebhookRouter(): builds the GitHub webhook router
 */

import "node:crypto";

import { TaskQueue } from "./task_queue";
import express from "express";
import pino from "pino";

const logger = pino.default({ name: "webhooks" });

export function verifySignature(secret: string, payload: string, signature: string): boolean {
  /**
   * Verifies the HMAC-SHA256 signature GitHub sends with each delivery.
   *
   * @param secret - Webhook secret shared with GitHub.
   * @param payload - Raw request body.
   * @param signature - Value of the x-hub-signature-256 header.
   * @returns valid - True when the signature matches.
   */
  const expected = `sha256=${crypto.createHmac("sha256", secret).update(payload).digest("hex")}`;
  if (expected.length !== signature.length) {
    return false;
  }
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature));
}

export function createWebhookRouter(secret: string, queue: TaskQueue): express.Router {
  /**
   * Builds the webhook router bound to a secret and a run queue.
   *
   * @param secret - Webhook secret shared with GitHub.
   * @param queue - Queue receiving issue-triggered runs.
   * @returns router - Express router handling GitHub deliveries.
   */
  const router = express.Router();

  router.post("/webhooks/github", async (req, res) => {
    const signature = req.header("x-hub-signature-256") ?? "";
    const payload = JSON.stringify(req.body);
    if (!verifySignature(secret, payload, signature)) {
      res.status(401).json({ error: "bad signature" });
      return;
    }
    const event = req.header("x-github-event");
    if (event === "issues" && req.body.action === "opened") {
      const issue = req.body.issue;
      logger.info({ issue: issue.number }, "issue opened; enqueueing run");
      queue.enqueue(`issue-${issue.number}`, async () => {
        logger.info({ issue: issue.number }, "issue run started");
      });
    }
    res.status(202).json({ accepted: true });
  });

  return router;
}

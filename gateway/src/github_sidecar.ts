#!/usr/bin/env ts-node
/**
 * github_sidecar.ts --- git and GitHub API operations for agent runs
 *
 * Contains:
 *   SidecarConfig: repo coordinates and credentials
 *   cloneRepo(): shallow-clones the target repository
 *   createBranch(): creates the agent working branch
 *   commitAndPush(): commits the tree and pushes the branch
 *   withRetry(): retries a failing operation immediately
 *   createDraftPr(): opens a draft pull request
 *   PrFlowResult: outcome of the PR creation flow
 *   createPrFromRun(): clone, branch, commit, push, open draft PR
 */

import { exec } from "node:child_process";
import { promisify } from "node:util";

import { Octokit } from "@octokit/rest";
import pino from "pino";

const run = promisify(exec);
const logger = pino.default({ name: "github-sidecar" });

const BRANCH_PREFIX = "shipwright/";
const CLONE_DEPTH = 1;

export interface SidecarConfig {
  repoUrl: string;
  workDir: string;
  githubToken: string;
  baseBranch: string;
}

export async function cloneRepo(config: SidecarConfig, taskId: string): Promise<string> {
  /**
   * Shallow-clones the target repository for one task.
   *
   * @param config - Repo coordinates and credentials.
   * @param taskId - Task the clone belongs to.
   * @returns dest - Local path of the fresh clone.
   */
  const dest = `${config.workDir}/${taskId}`;
  await run(`git clone --depth ${CLONE_DEPTH} --branch ${config.baseBranch} ${config.repoUrl} ${dest}`);
  return dest;
}

export async function createBranch(repoDir: string, taskId: string): Promise<string> {
  /**
   * Creates the agent working branch in a clone.
   *
   * @param repoDir - Local clone to branch in.
   * @param taskId - Task the branch belongs to.
   * @returns branch - Name of the new branch.
   */
  const branch = `${BRANCH_PREFIX}${taskId}`;
  await run(`git -C ${repoDir} checkout -b ${branch}`);
  return branch;
}

export async function commitAndPush(
  repoDir: string,
  branch: string,
  message: string,
): Promise<void> {
  /**
   * Commits the working tree and pushes the branch to origin.
   *
   * @param repoDir - Local clone to commit in.
   * @param branch - Branch to push.
   * @param message - Commit message.
   */
  await run(`git -C ${repoDir} add -A`);
  await run(`git -C ${repoDir} commit -m "${message}"`);
  await run(`git -C ${repoDir} push -u origin ${branch}`);
}

async function withRetry<T>(fn: () => Promise<T>, attempts = 3): Promise<T> {
  /**
   * Retries a failing operation a fixed number of times, immediately.
   *
   * @param fn - Operation to retry.
   * @param attempts - Maximum attempts before giving up.
   * @returns result - First successful result.
   */
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

export async function createDraftPr(
  config: SidecarConfig,
  branch: string,
  title: string,
  body: string,
): Promise<string | null> {
  /**
   * Opens a draft pull request for the agent's branch.
   *
   * @param config - Repo coordinates and credentials.
   * @param branch - Branch holding the agent's work.
   * @param title - PR title.
   * @param body - PR body.
   * @returns url - HTML URL of the new PR, or null when creation failed.
   */
  try {
    return await withRetry(async () => {
      const octokit = new Octokit({ auth: config.githubToken });
      const [owner, repo] = config.repoUrl.split("/").slice(-2);
      const response = await octokit.pulls.create({
        owner,
        repo: repo.replace(/\.git$/, ""),
        head: branch,
        base: config.baseBranch,
        title,
        body,
        draft: true,
      });
      return response.data.html_url;
    });
  } catch (error) {
    logger.warn({ err: error }, "draft PR creation failed; continuing without PR");
    return null;
  }
}

export interface PrFlowResult {
  prUrl: string | null;
  branch: string;
}

export async function createPrFromRun(
  config: SidecarConfig,
  taskId: string,
  taskSummary: string,
): Promise<PrFlowResult> {
  /**
   * Runs the full flow: clone, branch, commit, push, open draft PR.
   *
   * @param config - Repo coordinates and credentials.
   * @param taskId - Task the run belongs to.
   * @param taskSummary - One-line summary used as commit and PR title.
   * @returns result - PR URL and branch name.
   */
  const repoDir = await cloneRepo(config, taskId);
  const branch = await createBranch(repoDir, taskId);
  await commitAndPush(repoDir, branch, taskSummary);
  const prUrl = await createDraftPr(config, branch, taskSummary, "");
  return { prUrl, branch };
}

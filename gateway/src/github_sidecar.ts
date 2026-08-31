#!/usr/bin/env ts-node
/**
 * github_sidecar.ts --- git and GitHub API operations for agent runs
 *
 * Contains:
 *   git(): runs one git command without a shell
 *   SidecarConfig: repo coordinates and credentials
 *   cloneRepo(): shallow-clones the target repository
 *   RepoCoordinates: owner and repo name of a repository
 *   repoCoordinates(): splits a repo URL into owner and repo
 *   createBranch(): creates the agent working branch
 *   commitAndPush(): commits the tree and pushes the branch
 *   createDraftPr(): opens a draft pull request
 *   PrFlowResult: outcome of the PR creation flow
 *   createPrFromRun(): clone, branch, commit, push, open draft PR
 *   batchGetFileContents(): fetches many files in one GraphQL query
 *   renderPrBody(): renders the PR body with test evidence
 *   getRefSha(): resolves a ref to a SHA, cached
 *   TreeEntry: one file to commit
 *   commitFiles(): commits many files as one tree
 *   octokitFor(): memoized Octokit client per token
 *   markPrReady(): flips a draft PR to ready-for-review
 *   getDefaultBranch(): resolves the default branch, cached
 *   deleteBranch(): deletes a remote branch on cleanup
 *   mapWithLimit(): maps items with bounded concurrency
 *   findOpenPr(): finds an already-open PR for a branch
 *   RunStats: aggregated run statistics
 *   renderRunStats(): renders stats for the PR body
 *   requestReviews(): requests reviews from the team pool
 *   countApiCall(): counts one API call
 *   apiCallReport(): reports per-operation counts
 *   closesIssueLine(): builds the Closes trailer
 */

import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { RequestQueue } from "./rate_limiter";
import { Octokit } from "@octokit/rest";
import pino from "pino";

const execFileAsync = promisify(execFile);
const logger = pino({ name: "github-sidecar" });

const BRANCH_PREFIX = "shipwright/";
const mutationQueue = new RequestQueue();
const CLONE_DEPTH = 1;
const API_TIMEOUT_MS = 20_000;
const DEFAULT_REVIEWERS: string[] = [];

async function git(args: string[]): Promise<void> {
  /**
   * Runs one git command with its arguments passed as an argv array.
   *
   * Never build a shell string here: task ids, branch names and commit
   * messages all originate in request bodies.
   *
   * @param args - Argument vector handed to the git binary.
   */
  await execFileAsync("git", args);
}

export interface SidecarConfig {
  repoUrl: string;
  workDir: string;
  githubToken: string;
  baseBranch: string;
}

export interface RepoCoordinates {
  owner: string;
  repo: string;
}

export function repoCoordinates(repoUrl: string): RepoCoordinates {
  /**
   * Splits a repository URL into its owner and repo name.
   *
   * @param repoUrl - Clone or browse URL of the repository.
   * @returns coordinates - Owner and repo name, without any .git suffix.
   */
  const [owner, repo] = repoUrl.split("/").slice(-2);
  if (owner === undefined || repo === undefined) {
    throw new Error(`unparseable repo url: ${repoUrl}`);
  }
  return { owner, repo: repo.replace(/\.git$/, "") };
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
  await git([
    "clone",
    "--depth",
    String(CLONE_DEPTH),
    "--branch",
    config.baseBranch,
    config.repoUrl,
    dest,
  ]);
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
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const branch = `${BRANCH_PREFIX}${stamp}-${taskId}`;
  await git(["-C", repoDir, "checkout", "-b", branch]);
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
  await git(["-C", repoDir, "add", "-A"]);
  const trailer = `\n\nTask-Id: ${branch.replace(BRANCH_PREFIX, "")}`;
  await git(["-C", repoDir, "commit", "-m", `${message}${trailer}`]);
  await git(["-C", repoDir, "push", "-u", "origin", branch]);
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
  const existing = await findOpenPr(config, branch);
  if (existing !== null) {
    return existing;
  }
  return mutationQueue.enqueue(async () => {
    const octokit = octokitFor(config.githubToken);
    const { owner, repo } = repoCoordinates(config.repoUrl);
    const response = await octokit.pulls.create({
      owner,
      repo,
      head: branch,
      base: config.baseBranch,
      title,
      body,
      draft: true,
    });
    await octokit.issues.addLabels({
      owner,
      repo,
      issue_number: response.data.number,
      labels: ["shipwright"],
    });
    return response.data.html_url;
  });
}

export interface PrFlowResult {
  prUrl: string | null;
  branch: string;
}

export async function createPrFromRun(
  config: SidecarConfig,
  taskId: string,
  taskSummary: string,
  testsRun: string[] = [],
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
  const prUrl = await createDraftPr(
    config,
    branch,
    taskSummary,
    renderPrBody(taskSummary, testsRun),
  );
  return { prUrl, branch };
}

export async function batchGetFileContents(
  config: SidecarConfig,
  paths: string[],
): Promise<Map<string, string>> {
  /**
   * Fetches many files in one GraphQL query instead of one REST call each.
   *
   * @param config - Repo coordinates and credentials.
   * @param paths - Repo-relative file paths to fetch.
   * @returns contents - Mapping of path to file text.
   */
  const octokit = octokitFor(config.githubToken);
  const { owner, repo } = repoCoordinates(config.repoUrl);
  const entries = paths
    .map((path, i) => `f${i}: object(expression: "HEAD:${path}") { ... on Blob { text } }`)
    .join("\n");
  const query = `query { repository(owner: "${owner}", name: "${repo}") { ${entries} } }`;
  const response = await octokit.graphql<{ repository: Record<string, { text?: string }> }>(query);
  const contents = new Map<string, string>();
  paths.forEach((path, i) => {
    contents.set(path, response.repository[`f${i}`]?.text ?? "");
  });
  return contents;
}

export function renderPrBody(taskSummary: string, testsRun: string[]): string {
  /**
   * Renders the PR body with a summary and test evidence placeholder.
   *
   * @param taskSummary - One-line summary of the change.
   * @param testsRun - Test commands the agent ran.
   * @returns body - Markdown PR body.
   */
  const lines = [`## Summary`, ``, taskSummary, ``, `## Tests`, ``];
  for (const test of testsRun) {
    lines.push(`- \`${test}\``);
  }
  const trailer = closesIssueLine(null);
  if (trailer !== "") {
    lines.push("", trailer);
  }
  lines.push("", "Opened by shipwright as a draft.");
  return lines.join("\n");
}

const refsCache = new Map<string, { sha: string; fetchedAt: number }>();
const prUrlCache = new Map<string, { url: string; fetchedAt: number }>();
const REFS_TTL_MS = 60_000;
const MAX_BATCH_PATHS = 40;

export async function getRefSha(config: SidecarConfig, ref: string): Promise<string> {
  /**
   * Resolves a ref to a commit SHA, cached for a minute to save API calls.
   *
   * @param config - Repo coordinates and credentials.
   * @param ref - Ref to resolve.
   * @returns sha - Commit SHA the ref points at.
   */
  const cacheKey = `${config.repoUrl}#${ref}`;
  const cached = refsCache.get(cacheKey);
  if (cached !== undefined && Date.now() - cached.fetchedAt < REFS_TTL_MS) {
    return cached.sha;
  }
  const octokit = octokitFor(config.githubToken);
  const { owner, repo } = repoCoordinates(config.repoUrl);
  const response = await octokit.git.getRef({
    owner,
    repo,
    ref: `heads/${ref}`,
  });
  const sha = response.data.object.sha;
  refsCache.set(cacheKey, { sha, fetchedAt: Date.now() });
  return sha;
}

export interface TreeEntry {
  path: string;
  content: string;
}

export async function commitFiles(
  config: SidecarConfig,
  branch: string,
  entries: TreeEntry[],
  message: string,
): Promise<void> {
  /**
   * Commits many files as one tree/commit pair instead of one commit per file.
   *
   * @param config - Repo coordinates and credentials.
   * @param branch - Branch to commit onto.
   * @param entries - Files to write.
   * @param message - Commit message.
   */
  const octokit = octokitFor(config.githubToken);
  const { owner, repo } = repoCoordinates(config.repoUrl);
  const baseSha = await getRefSha(config, branch);
  const tree = await octokit.git.createTree({
    owner,
    repo,
    base_tree: baseSha,
    tree: entries.map((entry) => ({
      path: entry.path,
      mode: "100644" as const,
      type: "blob" as const,
      content: entry.content,
    })),
  });
  const commit = await octokit.git.createCommit({
    owner,
    repo,
    message,
    tree: tree.data.sha,
    parents: [baseSha],
  });
  await octokit.git.updateRef({
    owner,
    repo,
    ref: `heads/${branch}`,
    sha: commit.data.sha,
  });
}

const octokitByToken = new Map<string, Octokit>();

function octokitFor(token: string): Octokit {
  /**
   * Returns a memoized Octokit client per token.
   *
   * @param token - GitHub credential.
   * @returns client - Octokit instance bound to that credential.
   */
  const cached = octokitByToken.get(token);
  if (cached !== undefined) {
    return cached;
  }
  const client = new Octokit({ auth: token });
  octokitByToken.set(token, client);
  return client;
}

export async function markPrReady(config: SidecarConfig, prUrl: string): Promise<void> {
  /**
   * Flips a draft PR to ready-for-review after quality gates pass.
   *
   * @param config - Repo coordinates and credentials.
   * @param prUrl - HTML URL of the draft PR.
   */
  const octokit = octokitFor(config.githubToken);
  const match = prUrl.match(/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/);
  if (match === null) {
    throw new Error(`unparseable PR url: ${prUrl}`);
  }
  await octokit.pulls.update({
    owner: match[1]!,
    repo: match[2]!,
    pull_number: Number(match[3]),
    draft: false,
  });
}

let defaultBranchCache: string | null = null;

export async function getDefaultBranch(config: SidecarConfig): Promise<string> {
  /**
   * Resolves the repository's default branch via the API, cached per process.
   *
   * @param config - Repo coordinates and credentials.
   * @returns branch - Default branch name.
   */
  if (defaultBranchCache !== null) {
    return defaultBranchCache;
  }
  const octokit = octokitFor(config.githubToken);
  const { owner, repo } = repoCoordinates(config.repoUrl);
  const response = await octokit.repos.get({ owner, repo });
  defaultBranchCache = response.data.default_branch;
  return defaultBranchCache;
}

export async function deleteBranch(config: SidecarConfig, branch: string): Promise<void> {
  /**
   * Deletes a remote branch once its task is fully cleaned up.
   *
   * @param config - Repo coordinates and credentials.
   * @param branch - Branch to delete.
   */
  const octokit = octokitFor(config.githubToken);
  const { owner, repo } = repoCoordinates(config.repoUrl);
  await octokit.git.deleteRef({
    owner,
    repo,
    ref: `heads/${branch}`,
  });
}

export async function mapWithLimit<T, R>(
  items: T[],
  limit: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  /**
   * Maps items with bounded concurrency to stay under rate limits.
   *
   * @param items - Items to map.
   * @param limit - Maximum in-flight operations.
   * @param fn - Async mapping function.
   * @returns results - Mapped results in input order.
   */
  const results: R[] = new Array(items.length);
  let cursor = 0;
  async function worker(): Promise<void> {
    while (cursor < items.length) {
      const index = cursor;
      cursor += 1;
      // index < items.length by the loop guard; items[index] is defined
      results[index] = await fn(items[index]!);
    }
  }
  await Promise.all(Array.from({ length: limit }, worker));
  return results;
}

export async function findOpenPr(config: SidecarConfig, branch: string): Promise<string | null> {
  /**
   * Finds an already-open PR for a branch, if one exists.
   *
   * @param config - Repo coordinates and credentials.
   * @param branch - Branch to look up.
   * @returns url - HTML URL of the open PR, or null.
   */
  const octokit = octokitFor(config.githubToken);
  const { owner, repo } = repoCoordinates(config.repoUrl);
  const cached = prUrlCache.get(`${owner}:${branch}`);
  if (cached !== undefined && Date.now() - cached.fetchedAt < REFS_TTL_MS) {
    return cached.url;
  }
  const response = await octokit.pulls.list({
    owner,
    repo,
    head: `${owner}:${branch}`,
    state: "open",
  });
  // length checked above: data[0] exists whenever the list is non-empty
  const url = response.data.length > 0 ? response.data[0]!.html_url : null;
  if (url !== null) {
    prUrlCache.set(`${owner}:${branch}`, { url, fetchedAt: Date.now() });
  }
  return url;
}

export interface RunStats {
  steps: number;
  durationS: number;
  costUsd: number;
}

export function renderRunStats(stats: RunStats): string {
  /**
   * Renders run statistics as a Markdown details block for the PR body.
   *
   * @param stats - Aggregated run statistics.
   * @returns block - Markdown details block.
   */
  return [
    "<details><summary>agent run stats</summary>",
    "",
    `- steps: ${stats.steps}`,
    `- duration: ${stats.durationS.toFixed(1)}s`,
    `- model cost: $${stats.costUsd.toFixed(4)}`,
    "",
    "</details>",
  ].join("\n");
}

export async function requestReviews(
  config: SidecarConfig,
  prUrl: string,
  reviewers: string[] = DEFAULT_REVIEWERS,
): Promise<void> {
  /**
   * Requests reviews on a PR from the team's reviewer pool.
   *
   * @param config - Repo coordinates and credentials.
   * @param prUrl - HTML URL of the PR.
   * @param reviewers - GitHub logins to request; defaults to the team pool.
   */
  if (reviewers.length === 0) {
    return;
  }
  const octokit = octokitFor(config.githubToken);
  const match = prUrl.match(/github\.com\/([^/]+)\/([^/]+)\/pull\/(\d+)/);
  if (match === null) {
    throw new Error(`unparseable PR url: ${prUrl}`);
  }
  await octokit.pulls.requestReviewers({
    owner: match[1]!,
    repo: match[2]!,
    pull_number: Number(match[3]),
    reviewers,
  });
}

const apiCalls = new Map<string, number>();

export function countApiCall(operation: string): void {
  /**
   * Increments the per-operation API call counter.
   *
   * @param operation - Operation name to count.
   */
  apiCalls.set(operation, (apiCalls.get(operation) ?? 0) + 1);
}

export function apiCallReport(): Record<string, number> {
  /**
   * Reports per-operation API call counts for the current process.
   *
   * @returns report - Mapping of operation to call count.
   */
  return Object.fromEntries(apiCalls);
}

export function closesIssueLine(issueUrl: string | null): string {
  /**
   * Builds the "Closes #n" trailer linking the PR to its trigger issue.
   *
   * @param issueUrl - URL of the triggering issue, when any.
   * @returns line - Trailer line, or empty string.
   */
  if (issueUrl === null) {
    return "";
  }
  const number = issueUrl.split("/").pop();
  return `Closes #${number}`;
}

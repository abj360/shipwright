#!/usr/bin/env ts-node
/**
 * github_sidecar.ts --- git and GitHub API operations for agent runs
 *
 * Contains:
 *   SidecarConfig: repo coordinates and credentials
 *   cloneRepo(): shallow-clones the target repository
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
 */

import { exec } from "node:child_process";
import { promisify } from "node:util";

import { RequestQueue } from "./rate_limiter";
import { Octokit } from "@octokit/rest";
import pino from "pino";

const run = promisify(exec);
const logger = pino.default({ name: "github-sidecar" });

const BRANCH_PREFIX = "shipwright/";
const mutationQueue = new RequestQueue();
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
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const branch = `${BRANCH_PREFIX}${stamp}-${taskId}`;
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
  const trailer = "\n\nTask-Id: " + branch.replace(BRANCH_PREFIX, "");
  await run(`git -C ${repoDir} commit -m "${message}${trailer}"`);
  await run(`git -C ${repoDir} push -u origin ${branch}`);
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
  return mutationQueue.enqueue(async () => {
    const octokit = octokitFor(config.githubToken);
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
  const prUrl = await createDraftPr(config, branch, taskSummary, renderPrBody(taskSummary, []));
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
  const [owner, repo] = config.repoUrl.split("/").slice(-2);
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
  lines.push("", "Opened by shipwright as a draft.");
  return lines.join("\n");
}

const refsCache = new Map<string, { sha: string; fetchedAt: number }>();
const prUrlCache = new Map<string, { url: string; fetchedAt: number }>();
const REFS_TTL_MS = 60_000;

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
  const [owner, repo] = config.repoUrl.split("/").slice(-2);
  const response = await octokit.git.getRef({
    owner,
    repo: repo.replace(/\.git$/, ""),
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
  const [owner, repo] = config.repoUrl.split("/").slice(-2);
  const baseSha = await getRefSha(config, branch);
  const tree = await octokit.git.createTree({
    owner,
    repo: repo.replace(/\.git$/, ""),
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
    repo: repo.replace(/\.git$/, ""),
    message,
    tree: tree.data.sha,
    parents: [baseSha],
  });
  await octokit.git.updateRef({
    owner,
    repo: repo.replace(/\.git$/, ""),
    ref: `heads/${branch}`,
    sha: commit.data.sha,
  });
}

let octokitInstance: Octokit | null = null;

function octokitFor(token: string): Octokit {
  /**
   * Returns a memoized Octokit client per token.
   *
   * @param token - GitHub credential.
   * @returns client - Shared Octokit instance.
   */
  if (octokitInstance === null) {
    octokitInstance = new Octokit({ auth: token });
  }
  return octokitInstance;
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
  const [owner, repo] = config.repoUrl.split("/").slice(-2);
  const response = await octokit.repos.get({ owner, repo: repo.replace(/\.git$/, "") });
  defaultBranchCache = response.data.default_branch;
  return defaultBranchCache;
}

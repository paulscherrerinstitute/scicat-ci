#!/usr/bin/env node

const fs = require("fs");
require("dotenv").config({ path: "/home/node/app/.env" });

const HOST = process.env.SCICAT_HOST;
const INDEX = process.env.OPENSEARCH_INDEX;
const FUNCTIONAL_ACCOUNTS_FILE = "/home/node/app/functionalAccounts.json";

if (!HOST) fail("Missing required env var: SCICAT_HOST");
if (!INDEX) fail("Missing required env var: OPENSEARCH_INDEX");
if (!FUNCTIONAL_ACCOUNTS_FILE) fail("Missing required env var: FUNCTIONAL_ACCOUNTS_FILE");

const ADMIN_GROUPS = (process.env.ADMIN_GROUPS || "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);
if (ADMIN_GROUPS.length === 0) fail("ADMIN_GROUPS not found or empty in .env");

function fail(msg) {
  console.error(msg);
  process.exit(1);
}

const accounts = JSON.parse(fs.readFileSync(FUNCTIONAL_ACCOUNTS_FILE, "utf8"));
const account = accounts.find((a) => {
  const roles = Array.isArray(a.role) ? a.role : [a.role];
  return roles.some((r) => ADMIN_GROUPS.includes(r));
});
if (!account) fail("No functional account found for admin groups");
const USERNAME = account.username;
const PASSWORD = account.password;

const RETRIES = 30;
const DELAY_MS = 10_000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function retry(desc, fn, okCodes = [200, 201]) {
  for (let attempt = 1; attempt <= RETRIES; attempt++) {
    try {
      const resp = await fn();
      if (okCodes.includes(resp.status)) {
        return resp;
      }
      console.error(
        `[${desc}] attempt ${attempt}/${RETRIES} got ${resp.status}, retrying in ${DELAY_MS / 1000}s...`
      );
    } catch (err) {
      console.error(
        `[${desc}] attempt ${attempt}/${RETRIES} error: ${err.message}, retrying in ${DELAY_MS / 1000}s...`
      );
    }
    await sleep(DELAY_MS);
  }
  fail(`[${desc}] failed after ${RETRIES} attempts`);
}

async function main() {
  console.log("Waiting for SciCat BE health...");
  await retry("health", () => fetch(`${HOST}/api/v3/health`));

  console.log("Logging in...");
  const loginResp = await retry("login", () =>
    fetch(`${HOST}/api/v3/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: USERNAME, password: PASSWORD }),
    })
  );
  const { access_token: token } = await loginResp.json();
  const headers = { Authorization: `Bearer ${token}` };

  console.log(`Deleting index ${INDEX} (if it exists)...`);
  const qs = new URLSearchParams({ index: INDEX }).toString();
  const delResp = await retry(
    "delete-index",
    () =>
      fetch(`${HOST}/api/v3/opensearch/delete-index?${qs}`, {
        method: "POST",
        headers,
      }),
    [200, 400]
  );
  if (delResp.status === 400) {
    console.log(`Index ${INDEX} did not exist, nothing to delete.`);
  }

  console.log(`Creating index ${INDEX}...`);
  await retry("create-index", () =>
    fetch(`${HOST}/api/v3/opensearch/create-index`, {
      method: "POST",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ index: INDEX }),
    })
  );

  console.log("Syncing database into OpenSearch...");
  const syncResp = await retry("sync-database", () =>
    fetch(`${HOST}/api/v3/opensearch/sync-database?${qs}`, {
      method: "POST",
      headers,
    })
  );
  const result = await syncResp.json();
  console.log(
    `Synced ${result.successful} of ${result.total} documents ` +
      `(${result.failed} failed, took ${result.time}ms).`
  );
}

main().catch((err) => fail(err.stack || err.message));

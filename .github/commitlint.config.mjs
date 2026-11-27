import { readdirSync } from "node:fs";

const dirs = (path) =>
  readdirSync(new URL(path, import.meta.url), { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name);

export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "header-max-length": [2, "always", 72],
    "body-max-line-length": [0],
    "footer-max-line-length": [2, "always", 72],
    "body-empty": [2, "never"],
    "scope-enum": [
      2,
      "always",
      [...new Set([
        // Deployed components, read from the folders so the list never drifts.
        ...dirs("../helm/configs/"),
        // Code living in this repo.
        "proposals",
        "retention",
        "scicat-to-pss",
        "curation",
        // Cross-cutting.
        "ci",
        "deps",
        "renovate",
      ])],
    ],
  },
};

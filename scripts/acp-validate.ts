// acp-validate.ts — ACP document validator (M70 validators / ADR-24)
//
// Runs the deterministic /acp-validate checks against the project:
//   - version consistency across version-bearing files (Step 2c)
//   - file pointers in progress.yaml resolve on disk (Step 2f)
//   - milestone doc **Status** agrees with progress.yaml status (Step 2e)
//
// Uses js-yaml (YAML parse) + gray-matter (markdown frontmatter). Exits 1 on
// hard errors, 0 otherwise. Soft mismatches print as warnings but do not fail.
// No product-stack knowledge — pure ACP document tooling.

import fs from "fs";
import * as yaml from "js-yaml";
import matter from "gray-matter";
import path from "path";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(HERE, "..");

let errors = 0;
let warnings = 0;

function loadYaml(rel: string): object | null {
  const abs = path.join(REPO_ROOT, rel);
  if (!fs.existsSync(abs)) {
    console.log(`ERROR: missing ${rel}`);
    errors++;
    return null;
  }
  try {
    return yaml.load(fs.readFileSync(abs, "utf8"));
  } catch (e) {
    console.log(`ERROR: YAML parse failure in ${rel}: ${String(e).split("\n")[0]}`);
    errors++;
    return null;
  }
}

// ── Step 2c: version consistency ───────────────────────────────────────────
const progress = loadYaml("agent/progress.yaml");
const canonical = progress?.project?.version;
if (!canonical) {
  console.log("ERROR: agent/progress.yaml → project.version missing");
  errors++;
} else {
  console.log(`🔍 Version Consistency (canonical: ${canonical})`);
  // Hard: CHANGELOG latest entry
  const changelogPath = path.join(REPO_ROOT, "CHANGELOG.md");
  if (fs.existsSync(changelogPath)) {
    const m = fs.readFileSync(changelogPath, "utf8").match(/^## \[(\d+\.\d+\.\d+)\]/m);
    if (!m) {
      console.log(`ERROR: CHANGELOG.md has no ## [x.y.z] entry`);
      errors++;
    } else if (m[1] !== canonical) {
      console.log(`ERROR: CHANGELOG.md ${m[1]} != canonical ${canonical}`);
      errors++;
    } else {
      console.log(`  ✅ CHANGELOG.md: ${m[1]}`);
    }
  } else {
    console.log("ERROR: CHANGELOG.md missing");
    errors++;
  }
}

if (progress?.milestones) {
  // ── Step 2f: file pointers resolve ───────────────────────────────────────
  for (const ms of progress.milestones) {
    const rel = ms.file;
    if (!rel || rel === "null") continue;
    const abs = path.join(REPO_ROOT, rel);
    if (!fs.existsSync(abs)) {
      console.log(`ERROR: milestone ${ms.id} file pointer dangling: ${rel}`);
      errors++;
    }
  }

  // ── Step 2e: cross-layer status consistency ──────────────────────────────
  const norm = (s: string) => {
    const v = (s || "").toLowerCase().trim();
    if (v === "active") return "in_progress";
    if (v === "implemented" || v === "done") return "completed";
    return v;
  };
  for (const ms of progress.milestones) {
    const rel = ms.file;
    if (!rel || rel === "null") continue;
    const abs = path.join(REPO_ROOT, rel);
    if (!fs.existsSync(abs)) continue; // already reported as dangling
    const gm = matter(fs.readFileSync(abs, "utf8"));
    // Status lives in a body line "**Status**: completed" (or "**Status:** Completed").
    const statusMatch = gm.content.match(/\*\*Status\b[^A-Za-z\n]*([A-Za-z_]+)/);
    if (!statusMatch) {
      console.log(`WARN: milestone doc ${ms.id} has no **Status** field`);
      warnings++;
      continue;
    }
    if (norm(statusMatch[1]) !== norm(String(ms.status))) {
      console.log(
        `ERROR: status drift for ${ms.id}: doc='${statusMatch[1]}' progress.yaml='${ms.status}'`,
      );
      errors++;
    }
  }
}

console.log(`\nexecuted checks: version + pointers + status`);
if (errors > 0) {
  console.log(`[acp-validate.ts] FAIL | ${errors} error(s), ${warnings} warning(s)`);
  process.exit(1);
}
console.log(`[acp-validate.ts] PASS | ${warnings} warning(s)`);

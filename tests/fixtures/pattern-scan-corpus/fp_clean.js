// FALSE-POSITIVE fixture for acp.pattern-scan.py — this file must stay CLEAN.
// env read used for local config, no network sink in the window:
const PORT = parseInt(process.env.LLM_MONITOR_PORT || "8090", 10);
const { execFileSync } = require("child_process");

// literal argv, not interpolated:
execFileSync("git", ["rev-parse", "HEAD"]);

// static GET, no credential in URL or logs:
async function load() {
  const res = await fetch("/api/stats");
  return res.json();
}

// logging a non-secret config value:
console.log("serving on port", PORT);

// dynamic require that IS suppressed with a reason (must not fire, must not crash):
const pluginName = "safe";
require(pluginName); // acp-integrity-ignore: IG-25 - reviewed plugin registry lookup

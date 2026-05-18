#!/usr/bin/env node

const fs = require("fs");
const path = require("path");
const os = require("os");
const { execSync } = require("child_process");

const SKILL_NAME = "strict-flow";
const SKILL_SOURCE = path.resolve(__dirname);

const AGENT_CONFIG = {
  codex: {
    dirs: [
      path.join(os.homedir(), ".agents", "skills"),   // new unified path (CLI + IDE + App)
      path.join(os.homedir(), ".codex", "skills"),     // legacy CLI path
    ],
    commands: ["codex"],
    label: "Codex",
  },
  claude: {
    dirs: [
      path.join(os.homedir(), ".claude", "skills"),
    ],
    commands: ["claude"],
    label: "Claude Code",
  },
  opencode: {
    dirs: [
      path.join(os.homedir(), ".opencode", "skills"),
    ],
    commands: ["opencode"],
    label: "OpenCode",
  },
};

// Files that should not be copied to skill directories
const EXCLUDE_FILES = new Set(["install.js", "package.json", "package-lock.json"]);

function copyRecursive(src, dest) {
  if (!fs.existsSync(dest)) {
    fs.mkdirSync(dest, { recursive: true });
  }
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    if (EXCLUDE_FILES.has(entry.name)) continue;
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyRecursive(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function detectAgents() {
  return Object.entries(AGENT_CONFIG).filter(([, cfg]) => {
    for (const cmd of cfg.commands) {
      try {
        execSync(`which ${cmd}`, { stdio: "pipe" });
        return true;
      } catch {}
    }
    for (const dir of cfg.dirs) {
      if (fs.existsSync(path.dirname(dir))) return true;
    }
    return false;
  });
}

function installTo(agentKey) {
  const cfg = AGENT_CONFIG[agentKey];
  if (!cfg) {
    console.error(`  Unknown agent: ${agentKey}`);
    return false;
  }

  let installed = false;
  for (const dir of cfg.dirs) {
    const dest = path.join(dir, SKILL_NAME);
    try {
      copyRecursive(SKILL_SOURCE, dest);
      console.log(`  ✓ ${cfg.label} → ${dest}`);
      installed = true;
    } catch (err) {
      console.error(`  ✗ ${cfg.label} install failed (${dest}): ${err.message}`);
    }
  }

  if (!installed) {
    console.error(`  ✗ ${cfg.label}: no writable skill directory found`);
  }
  return installed;
}

function uninstallFrom(agentKey) {
  const cfg = AGENT_CONFIG[agentKey];
  if (!cfg) return 0;

  let removed = 0;
  for (const dir of cfg.dirs) {
    const dest = path.join(dir, SKILL_NAME);
    if (fs.existsSync(dest)) {
      fs.rmSync(dest, { recursive: true, force: true });
      console.log(`  ✓ Removed from ${cfg.label} (${dest})`);
      removed++;
    }
  }
  return removed;
}

// --- main ---

const args = process.argv.slice(2);
const helpFlag = args.includes("--help") || args.includes("-h");
const agentFlagIdx = args.indexOf("--agent");
const uninstallFlag = args.includes("--uninstall");

if (helpFlag) {
  console.log(`
strict-flow — lightweight three-gate workflow skill

Usage:
  npx strict-flow              Auto-detect and install to all available agents
  npx strict-flow --agent codex     Install to Codex (CLI + App)
  npx strict-flow --agent claude    Install to Claude Code
  npx strict-flow --agent all       Install to all supported agents
  npx strict-flow --uninstall       Remove from all agents
  npx strict-flow --help            Show this help

Supported agents: codex, claude, opencode
`);
  process.exit(0);
}

if (uninstallFlag) {
  console.log("\nUninstalling strict-flow...\n");
  let totalRemoved = 0;
  for (const key of Object.keys(AGENT_CONFIG)) {
    totalRemoved += uninstallFrom(key);
  }
  if (totalRemoved === 0) console.log("  (not installed anywhere)");
  console.log();
  process.exit(0);
}

// determine target agents
let targets;
if (agentFlagIdx !== -1 && args[agentFlagIdx + 1]) {
  const agent = args[agentFlagIdx + 1];
  if (agent === "all") {
    targets = Object.keys(AGENT_CONFIG);
  } else {
    targets = [agent];
  }
} else {
  const detected = detectAgents();
  if (detected.length > 0) {
    targets = detected.map(([key]) => key);
  } else {
    targets = Object.keys(AGENT_CONFIG);
  }
}

console.log(`\nInstalling strict-flow skill...\n`);
let success = 0;
for (const key of targets) {
  if (installTo(key)) success++;
}

if (success === 0) {
  console.error("\nNo agents installed. Install Codex, Claude Code, or OpenCode first.\n");
  process.exit(1);
}

console.log(`\nDone! Start a new session and say "strict flow" or "强制流程" to activate.\n`);

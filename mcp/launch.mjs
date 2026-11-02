import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const vitePath = path.join(root, "node_modules/vite/bin/vite.js");
const serverPath = path.join(root, "mcp/server.mjs");

async function main() {
  if (!existsSync(vitePath)) {
    throw new Error("MCP App dependencies are missing. Run `npm install` in the workspace.");
  }

  const build = spawnSync(process.execPath, [vitePath, "build"], {
    cwd: root,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "inherit"],
  });
  if (build.stdout) process.stderr.write(build.stdout);
  if (build.error) throw build.error;
  if (build.status !== 0) {
    throw new Error(`MCP App build failed with status ${build.status}.`);
  }

  const server = spawn(process.execPath, [serverPath, "--stdio"], {
    cwd: root,
    stdio: "inherit",
  });
  for (const signal of ["SIGINT", "SIGTERM"]) {
    process.on(signal, () => server.kill(signal));
  }
  const exitCode = await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.once("exit", (code) => resolve(code ?? 1));
  });
  process.exitCode = exitCode;
}

main().catch((error) => {
  console.error(`NKP MCP server startup failed: ${error.message}`);
  process.exitCode = 1;
});

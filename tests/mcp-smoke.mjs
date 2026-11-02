import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { LATEST_PROTOCOL_VERSION } from "@modelcontextprotocol/server";
import {
  createConfirmedContractMessage,
  sendConfirmedContract,
} from "../mcp/contract-message.js";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const proposedYaml = "app: hello-nkp\nreplicas: 2\n";
const message = createConfirmedContractMessage(proposedYaml);
assert(message.includes(`\`\`\`yaml\n${proposedYaml}`));
assert(message.includes("\n```"));
assert(message.includes("J'ai explicitement confirmé"));
assert(message.includes("autorise l'application de ces seules valeurs"));
assert(message.includes("Ne demande pas de nouvelle confirmation"));
let sentMessage;
await sendConfirmedContract(
  {
    getHostCapabilities: () => ({ message: { text: {} } }),
    sendMessage: async (params) => {
      sentMessage = params;
      return {};
    },
  },
  proposedYaml,
);
assert.equal(sentMessage.content[0].text, message);
await assert.rejects(
  sendConfirmedContract(
    {
      sendMessage: async () => {
        throw new Error("host message transport unavailable");
      },
    },
    proposedYaml,
  ),
  /host message transport unavailable/,
);
await assert.rejects(
  sendConfirmedContract(
    {
      getHostCapabilities: () => ({ message: { text: {} } }),
      sendMessage: async () => ({ isError: true }),
    },
    proposedYaml,
  ),
  /refusé d'envoyer/,
);

const child = spawn(process.execPath, ["mcp/launch.mjs"], {
  cwd: root,
  stdio: ["pipe", "pipe", "pipe"],
});
const pending = new Map();
const lines = createInterface({ input: child.stdout });
let requestId = 0;

lines.on("line", (line) => {
  let message;
  try {
    message = JSON.parse(line);
  } catch {
    for (const reject of pending.values()) {
      reject(new Error(`Unexpected non-MCP output on stdout: ${line}`));
    }
    pending.clear();
    return;
  }

  if (message.id !== undefined && pending.has(message.id)) {
    const handle = pending.get(message.id);
    pending.delete(message.id);
    handle(message);
  }
});

child.stderr.on("data", (chunk) => process.stderr.write(chunk));

function request(method, params) {
  const id = ++requestId;
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      pending.delete(id);
      reject(new Error(`Timed out waiting for MCP response to ${method}.`));
    }, 15000);
    pending.set(id, (message) => {
      clearTimeout(timeout);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    });
    child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", id, method, params })}\n`);
  });
}

function notify(method, params) {
  child.stdin.write(`${JSON.stringify({ jsonrpc: "2.0", method, params })}\n`);
}

try {
  await request("initialize", {
    protocolVersion: LATEST_PROTOCOL_VERSION,
    capabilities: {},
    clientInfo: { name: "nkp-contract-smoke-test", version: "1.0.0" },
  });
  notify("notifications/initialized", {});

  const tools = await request("tools/list", {});
  const toolNames = tools.tools.map((tool) => tool.name);
  assert(toolNames.includes("open_nkp_contract_form"));
  assert(toolNames.includes("validate_nkp_contract"));

  const opened = await request("tools/call", {
    name: "open_nkp_contract_form",
    arguments: {},
  });
  assert.equal(opened.structuredContent.kind, "initial");
  assert.equal(opened.structuredContent.contract.app, "hello-nkp");
  assert.equal(opened.structuredContent.appLocked, true);

  const resource = await request("resources/read", {
    uri: "ui://nkp-contract/configure-form.html",
  });
  assert(resource.contents[0].mimeType.includes("mcp-app"));
  assert(resource.contents[0].text.includes("<h1>AI Programmatic Platform</h1>"));
  assert(resource.contents[0].text.includes("Désactivé"));
  assert(resource.contents[0].text.includes("Confirmer et envoyer le YAML à Copilot"));
  assert(resource.contents[0].text.includes('id="delivery-result"'));
  assert(resource.contents[0].text.includes("YAML exact"));

  const valid = await request("tools/call", {
    name: "validate_nkp_contract",
    arguments: {
      contract: {
        app: "hello-nkp",
        owner: "vincent",
        env: "dev",
        archi: "stateless",
        runtime: "python",
        port: 8080,
        size: "S",
        backup: "none",
        tracing: true,
        expose: { type: "loadbalancer" },
        llm: "none",
        expires: "2099-12-31",
      },
    },
  });
  assert.equal(valid.structuredContent.valid, true);

  const invalid = await request("tools/call", {
    name: "validate_nkp_contract",
    arguments: {
      contract: {
        app: "hello-nkp",
        owner: "vincent",
        env: "prod",
        archi: "stateless",
        runtime: "python",
        port: 8080,
        size: "S",
        backup: "none",
        tracing: true,
        expose: { type: "loadbalancer" },
      },
    },
  });
  assert.equal(invalid.structuredContent.valid, false);
  assert(invalid.structuredContent.errors.some((error) => error.includes("cost_center")));
  console.log("MCP stdio, UI resource, and contract validation smoke test passed.");
} finally {
  if (child.exitCode === null && child.signalCode === null) {
    child.kill("SIGTERM");
    await new Promise((resolve) => child.once("exit", resolve));
  }
}

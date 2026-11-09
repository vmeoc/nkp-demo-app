import { spawnSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { McpServer } from "@modelcontextprotocol/server";
import { StdioServerTransport } from "@modelcontextprotocol/server/stdio";
import {
  registerAppResource,
  registerAppTool,
  RESOURCE_MIME_TYPE,
} from "@modelcontextprotocol/ext-apps/server";
import { parse } from "yaml";
import { z } from "zod";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const resourceUri = "ui://nkp-contract/configure-form.html";
const contractPath = path.join(root, "nkp-app.yaml");
const examplePath = path.join(root, "nkp-app.example.yaml");
const schemaPath = path.join(root, ".opencode/skills/nkp-deploy/schema.json");
const rendererPath = path.join(root, ".opencode/skills/nkp-deploy/render.py");
const appPath = path.join(root, "mcp-dist/mcp/contract-form.html");
const venvPython = path.join(root, ".venv/bin/python");

function readContractAndSchema() {
  const usingExample = !existsSync(contractPath);
  const sourcePath = usingExample ? examplePath : contractPath;
  const contract = parse(readFileSync(sourcePath, "utf8"));
  const schema = JSON.parse(readFileSync(schemaPath, "utf8"));

  if (!contract || typeof contract !== "object" || Array.isArray(contract)) {
    throw new Error(`${path.basename(sourcePath)} must contain a YAML object.`);
  }

  return { contract, schema, usingExample };
}

function validateContract(contract) {
  const python = existsSync(venvPython)
    ? venvPython
    : process.platform === "win32"
      ? "python"
      : "python3";
  const result = spawnSync(python, [rendererPath, "--validate-input"], {
    cwd: root,
    encoding: "utf8",
    input: JSON.stringify(contract),
    maxBuffer: 1024 * 1024,
  });

  if (result.error) {
    throw new Error(`Could not run NKP contract validation: ${result.error.message}`);
  }
  if (result.status !== 0) {
    throw new Error(result.stderr.trim() || `Contract validator exited with status ${result.status}.`);
  }

  return JSON.parse(result.stdout);
}

function toolResult(data) {
  return {
    content: [{ type: "text", text: JSON.stringify(data) }],
    structuredContent: data,
  };
}

const server = new McpServer({
  name: "nkp-contract-form",
  version: "1.0.0",
});

registerAppTool(
  server,
  "open_nkp_contract_form",
  {
    title: "Configurer le contrat NKP",
    description:
      "Ouvre le formulaire interactif du contrat NKP à partir des valeurs courantes et du schéma. Ne modifie aucun fichier et ne déploie pas.",
    inputSchema: z.object({}),
    _meta: { ui: { resourceUri } },
  },
  async () => {
    const data = readContractAndSchema();
    return toolResult({
      kind: "initial",
      ...data,
      appLocked: !data.usingExample && Boolean(data.contract.app),
    });
  },
);

registerAppTool(
  server,
  "validate_nkp_contract",
  {
    title: "Valider une proposition de contrat NKP",
    description:
      "Valide une proposition selon le schéma du dépôt et les règles de la plateforme NKP, sans écrire de fichiers.",
    inputSchema: z.object({
      contract: z.record(z.string(), z.unknown()),
    }),
    _meta: {},
  },
  async ({ contract }) => {
    const validation = validateContract(contract);
    return toolResult({ kind: "validation", ...validation });
  },
);

registerAppResource(
  server,
  resourceUri,
  resourceUri,
  { mimeType: RESOURCE_MIME_TYPE },
  async () => ({
    contents: [
      {
        uri: resourceUri,
        mimeType: RESOURCE_MIME_TYPE,
        text: readFileSync(appPath, "utf8"),
      },
    ],
  }),
);

await server.connect(new StdioServerTransport());

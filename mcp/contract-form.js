import { App } from "@modelcontextprotocol/ext-apps";
import { stringify } from "yaml";
import { sendConfirmedContract } from "./contract-message.js";
import "./contract-form.css";

const form = document.querySelector("#contract-form");
const status = document.querySelector("#status");
const statusText = status.querySelector(".status-text");
const review = document.querySelector("#review");
const messages = document.querySelector("#validation-messages");
const contractTable = document.querySelector("#contract-table");
const preview = document.querySelector("#contract-preview");
const deliveryResult = document.querySelector("#delivery-result");
const confirmButton = document.querySelector("#confirm");
const copyButton = document.querySelector("#copy");
const app = new App({ name: "NKP contract form", version: "1.0.0" });

let schema;
let currentContract;
let appLocked = false;
let confirmedYaml;

function setStatus(message) {
  statusText.textContent = message;
}

function fieldLabel(name, property) {
  return property.title || name;
}

function addHelp(container, text) {
  if (!text) return;
  const help = document.createElement("small");
  help.textContent = text;
  container.append(help);
}

function addSelect(container, name, property, value) {
  const select = document.createElement("select");
  select.name = name;
  select.required = true;

  for (const choice of property.oneOf || []) {
    const option = document.createElement("option");
    option.value = choice.const;
    option.textContent = choice.title
      ? `${choice.title} (${choice.const})`
      : choice.const;
    option.title = choice.description || "";
    option.disabled = Boolean(
      choice.description?.toLowerCase().includes("pas encore supporté"),
    );
    select.append(option);
  }
  select.value = value ?? property.oneOf?.[0]?.const ?? "";
  const choiceDescription = document.createElement("small");
  const updateDescription = () => {
    choiceDescription.textContent =
      property.oneOf?.find((choice) => choice.const === select.value)?.description || "";
  };
  select.addEventListener("change", updateDescription);
  updateDescription();
  container.append(select, choiceDescription);
}

function addInput(container, name, property, value, { locked = false } = {}) {
  if (property.oneOf) {
    addSelect(container, name, property, value);
    return;
  }

  if (property.type === "boolean") {
    const booleanSchema = {
      oneOf: [
        { const: true, title: "Activé" },
        { const: false, title: "Désactivé" },
      ],
    };
    addSelect(container, name, booleanSchema, value);
    return;
  }

  const input = document.createElement("input");
  input.name = name;
  input.type =
    name === "expires" || property.format === "date"
      ? "date"
      : property.type === "integer"
        ? "number"
        : "text";
  if (property.minimum !== undefined) input.min = String(property.minimum);
  if (property.maximum !== undefined) input.max = String(property.maximum);
  if (property.pattern) input.pattern = property.pattern;
  input.value = value ?? "";
  input.required = schema.required.includes(name);
  input.readOnly = locked;
  container.append(input);
}

function addField(parent, name, property, value, options = {}) {
  const wrapper = document.createElement("label");
  wrapper.className = "field";
  const title = document.createElement("span");
  title.className = "field-title";
  title.textContent = fieldLabel(name, property);
  wrapper.append(title);
  addInput(wrapper, name, property, value, options);
  addHelp(wrapper, property.description);
  parent.append(wrapper);
  return wrapper;
}

function addSection(title) {
  const section = document.createElement("fieldset");
  const legend = document.createElement("legend");
  legend.textContent = title;
  section.append(legend);
  form.append(section);
  return section;
}

function buildForm(data) {
  schema = data.schema;
  currentContract = data.contract;
  appLocked = data.appLocked;
  form.replaceChildren();

  const identity = addSection("Application");
  for (const name of ["app", "owner", "cost_center"]) {
    const property = schema.properties[name];
    if (property) {
      addField(identity, name, property, currentContract[name], {
        locked: name === "app" && appLocked,
      });
    }
  }

  const deployment = addSection("Déploiement");
  for (const name of ["env", "archi", "runtime", "port", "replicas", "size"]) {
    const property = schema.properties[name];
    addField(deployment, name, property, currentContract[name]);
  }

  const operations = addSection("Opérations");
  for (const name of ["backup", "tracing", "llm", "expires"]) {
    const property = schema.properties[name];
    if (property) addField(operations, name, property, currentContract[name]);
  }

  const exposeSection = addSection("Exposition");
  const exposeSchema = schema.properties.expose;
  const expose = currentContract.expose || {};
  addField(
    exposeSection,
    "type",
    exposeSchema.properties.type,
    expose.type,
  );
  for (const name of ["host", "ingress_class"]) {
    const property = exposeSchema.properties[name];
    if (property) {
      addField(exposeSection, name, property, expose[name]);
    }
  }

  const appNotice = document.createElement("p");
  appNotice.className = "notice";
  appNotice.textContent = appLocked
    ? "Le nom d'une application déjà configurée reste verrouillé pour éviter de créer une autre application par erreur."
    : "Le nom d'application deviendra le nom des ressources NKP ; évite de le changer après le déploiement.";
  identity.append(appNotice);

  form.hidden = false;
  updateConditionalFields();
  form.addEventListener("change", updateConditionalFields);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    validateProposal();
  });

  const validate = document.createElement("button");
  validate.type = "submit";
  validate.className = "primary";
  validate.textContent = "Vérifier et prévisualiser";
  form.append(validate);
}

function updateConditionalFields() {
  const environment = form.elements.namedItem("env")?.value;
  const runtime = form.elements.namedItem("runtime")?.value;
  const exposure = form.elements.namedItem("type")?.value;
  const costCenter = form.elements.namedItem("cost_center");
  const expiration = form.elements.namedItem("expires");
  const host = form.elements.namedItem("host");
  const ingressClass = form.elements.namedItem("ingress_class");
  const tracing = form.elements.namedItem("tracing");

  if (costCenter) costCenter.required = environment === "prod";
  if (expiration) expiration.disabled = environment === "prod";
  if (host) {
    host.required = exposure === "ingress";
    host.closest(".field").hidden = exposure !== "ingress";
  }
  if (ingressClass) {
    ingressClass.closest(".field").hidden = exposure !== "ingress";
    if (exposure === "ingress" && !ingressClass.value) {
      ingressClass.value = "kommander-traefik";
    }
  }
  if (tracing && runtime === "static") {
    tracing.value = "false";
    tracing.disabled = true;
  } else if (tracing) {
    tracing.disabled = false;
  }
}

function readContract() {
  const contract = {};
  const environment = form.elements.namedItem("env").value;
  for (const [name, property] of Object.entries(schema.properties)) {
    if (name === "expose") continue;
    if (name === "expires" && environment === "prod") continue;
    const input = form.elements.namedItem(name);
    if (!input) continue;

    if (property.type === "boolean") {
      contract[name] = input.value === "true";
    } else if (property.type === "integer") {
      if (input.value !== "") contract[name] = Number(input.value);
    } else if (input.value !== "") {
      contract[name] = input.value;
    }
  }

  const exposeType = form.elements.namedItem("type").value;
  contract.expose = { type: exposeType };
  if (exposeType === "ingress") {
    const host = form.elements.namedItem("host").value;
    const ingressClass = form.elements.namedItem("ingress_class").value;
    if (host) contract.expose.host = host;
    if (ingressClass) contract.expose.ingress_class = ingressClass;
  }

  return contract;
}

function displayMessages(validation) {
  messages.replaceChildren();
  const entries = [
    ...(validation.errors || []).map((text) => ({ text, kind: "error" })),
    ...(validation.warnings || []).map((text) => ({ text, kind: "warning" })),
  ];
  for (const entry of entries) {
    const item = document.createElement("li");
    item.className = entry.kind;
    item.textContent = entry.text;
    messages.append(item);
  }
}

function displayContractTable(contract) {
  const table = document.createElement("table");
  const header = document.createElement("thead");
  header.innerHTML = "<tr><th>Paramètre</th><th>Valeur proposée</th></tr>";
  table.append(header);
  const body = document.createElement("tbody");

  for (const [name, property] of Object.entries(schema.properties)) {
    const value = name === "expose" ? contract.expose : contract[name];
    const row = document.createElement("tr");
    const keyCell = document.createElement("th");
    keyCell.scope = "row";
    keyCell.textContent = property.title || name;
    const valueCell = document.createElement("td");
    valueCell.textContent =
      value === undefined && name === "replicas"
        ? `Non défini (défaut ${contract.env === "prod" || contract.env === "preprod" ? 2 : 1})`
        : value === undefined
          ? "Non défini"
          : typeof value === "object"
            ? Object.entries(value)
                .map(([key, item]) => `${key}: ${item}`)
                .join(", ")
            : String(value);
    row.append(keyCell, valueCell);
    body.append(row);
  }
  table.append(body);
  contractTable.replaceChildren(table);
}

async function validateProposal() {
  confirmButton.hidden = true;
  setStatus("Validation du contrat avec les règles NKP…");
  review.hidden = false;
  try {
    const contract = readContract();
    const result = await app.callServerTool({
      name: "validate_nkp_contract",
      arguments: { contract },
    });
    if (result.isError) {
      const detail = result.content
        ?.filter((item) => item.type === "text")
        .map((item) => item.text)
        .join("\n");
      throw new Error(detail || "Le serveur MCP a refusé la validation.");
    }
    const validation = result.structuredContent;
    if (!validation) {
      throw new Error("Le validateur n'a pas retourné de résultat structuré.");
    }
    displayMessages(validation);
    confirmedYaml = stringify(contract);
    preview.textContent = confirmedYaml;
    displayContractTable(contract);
    confirmButton.hidden = !validation.valid;
    setStatus(
      validation.valid
        ? `Contrat valide · ${validation.replicas} replica(s) effectif(s).`
        : "Corrige les erreurs avant de confirmer.",
    );
  } catch (error) {
    setStatus(`Échec de validation : ${error.message}`);
    confirmButton.hidden = true;
  }
}

confirmButton.addEventListener("click", async () => {
  if (!confirmedYaml) return;
  confirmButton.disabled = true;
  deliveryResult.hidden = false;
  deliveryResult.className = "delivery-result pending";
  deliveryResult.textContent = "Envoi du YAML confirmé au chat Copilot…";
  try {
    await sendConfirmedContract(app, confirmedYaml);
    deliveryResult.className = "delivery-result success";
    deliveryResult.textContent =
      "Le chat a accepté le YAML exact et l'autorisation de l'appliquer, de le pousser et de le déployer sans nouvelle confirmation.";
    setStatus("Contrat envoyé au chat Copilot.");
  } catch (error) {
    try {
      await navigator.clipboard.writeText(confirmedYaml);
      deliveryResult.className = "delivery-result fallback";
      deliveryResult.textContent =
        `Le chat n'a pas confirmé la réception du message (${error.message}). ` +
        "Le YAML a été copié : colle-le dans le chat pour continuer.";
      setStatus("Envoi non confirmé ; le YAML a été copié pour transfert manuel.");
    } catch (clipboardError) {
      deliveryResult.className = "delivery-result error";
      deliveryResult.textContent =
        `Envoi au chat impossible : ${error.message} Copie automatique également impossible : ${clipboardError.message}`;
      setStatus("Le contrat n'a pas été envoyé.");
    }
  } finally {
    confirmButton.disabled = false;
  }
});

copyButton.addEventListener("click", async () => {
  if (!confirmedYaml) return;
  try {
    await navigator.clipboard.writeText(confirmedYaml);
    setStatus("YAML copié.");
  } catch (error) {
    setStatus(`Copie impossible : ${error.message}`);
  }
});

app.ontoolresult = (result) => {
  try {
    const data = result.structuredContent;
    if (!data || data.kind !== "initial") return;
    buildForm(data);
    setStatus(data.usingExample
      ? "Contrat d'exemple chargé : le formulaire pourra proposer la création d'un contrat."
      : "Contrat actuel chargé. Les choix sont à jour avec le dépôt.");
  } catch (error) {
    setStatus(`Chargement du contrat impossible : ${error.message}`);
  }
};

app.connect().catch((error) => {
  setStatus(`Connexion à l'interface MCP impossible : ${error.message}`);
});

export function createConfirmedContractMessage(yaml) {
  return [
    "J'ai explicitement confirmé les valeurs exactes de ce contrat NKP dans le formulaire.",
    "Cette confirmation autorise l'application de ces seules valeurs à nkp-app.yaml, la génération des manifests, le push des changements nécessaires et le déploiement sur NKP.",
    "Ne demande pas de nouvelle confirmation avant le push ou le déploiement. Si une règle de la plateforme impose de modifier une valeur du contrat, fais confirmer la nouvelle proposition dans le formulaire.",
    "",
    "Contrat confirmé :",
    "```yaml",
    yaml,
    "```",
  ].join("\n");
}

export async function sendConfirmedContract(app, yaml) {
  const result = await app.sendMessage({
    role: "user",
    content: [{ type: "text", text: createConfirmedContractMessage(yaml) }],
  });
  if (result.isError) {
    throw new Error("Le client a refusé d'envoyer la confirmation au chat.");
  }

  return result;
}

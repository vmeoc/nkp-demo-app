# Hello NKP

Application Hello World en Python avec Flask, exposée sur le port 8080.

## Lancer localement

```bash
python3 -m pip install -r requirements.txt
python3 app.py
```

Puis ouvrir <http://localhost:8080>.

## Déploiement NKP

Le contrat `nkp-app.yaml` décrit la configuration de déploiement. Les manifests
Kubernetes sont générés depuis ce contrat par le workflow de déploiement NKP.

## Formulaire MCP dans VS Code

Le workspace fournit une MCP App expérimentale qui affiche un formulaire
interactif dans le chat Copilot de VS Code. Le serveur MCP s'exécute localement
en stdio ; il lit `nkp-app.yaml` et
`.github/skills/nkp-deploy/schema.json`, puis réutilise le validateur NKP.
Il n'écrit aucun fichier et ne lance aucun déploiement.

Prérequis : Node.js 20 ou plus, npm, et Python avec les dépendances du projet.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm install
```

Le workspace `.vscode/mcp.json` configure le serveur. Dans VS Code, recharge la
fenêtre si nécessaire, puis demande au chat Copilot d'ouvrir le formulaire du
contrat NKP. Le formulaire préremplit les valeurs existantes, propose les
paramètres à choix multiples sous forme de listes déroulantes, affiche les
contraintes et permet de vérifier puis prévisualiser les valeurs et le YAML
exact. Le bouton de confirmation envoie le YAML exact comme message au chat
Copilot et affiche le résultat. Si le client refuse l'envoi, le formulaire
essaie de copier le YAML pour transfert manuel et indique clairement ce repli ;
la confirmation autorise le chat à appliquer le contrat, générer, pousser et
déployer sans demander une approbation supplémentaire. Le serveur MCP lui-même
ne modifie aucun fichier.

La prise en charge MCP Apps dans VS Code est expérimentale et peut dépendre de
la version et des paramètres du client. Voir la
[documentation MCP de VS Code](https://code.visualstudio.com/docs/agent-customization/mcp-servers)
et son [annonce MCP Apps](https://code.visualstudio.com/blogs/2026/01/26/mcp-apps-support).
Sans rendu MCP Apps, le chat peut toujours utiliser les outils de validation du
serveur, mais pas afficher le formulaire intégré.

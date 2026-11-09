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

## Contrat NKP avec OpenCode

Le déploiement se pilote via le skill `nkp-deploy` (dans `.opencode/skills/`).
Le contrat `nkp-app.yaml` est discuté dans le chat sous forme d'un tableau
complet des options et valeurs proposées, puis validé par une approbation
explicite. La validation peut se faire avec `render.py --validate-input`
(contrat JSON sur stdin) ; le serveur MCP de validation (`validate_nkp_contract`)
reste également disponible si le serveur est configuré (VS Code).

Prérequis : Python avec les dépendances du projet.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Le serveur MCP (`mcp/`) reste fourni pour la validation (VS Code) et expose
l'outil `validate_nkp_contract`. Il ne modifie aucun fichier et ne lance aucun
déploiement. La prise en charge MCP Apps dans VS Code est expérimentale ; sous
OpenCode, le parcours texte est utilisé par défaut.

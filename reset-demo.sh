#!/usr/bin/env bash
# RAZ post-démo : remplace index.html par la page "demo loading" et pousse via GitOps.
# Retire aussi l'IP en dur (expose.ip) pour éviter le conflit MetalLB de sharing key.
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "Pas dans un repo Git"; exit 1; }
cd "$ROOT"

if [ -f .nkp/target.env ]; then
  set -a; . .nkp/target.env; set +a
fi

# 0. Arbre Git propre
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Arbre Git non propre. Committer ou stasher avant la RAZ."
  exit 1
fi

# 1. RAZ de la page
if [ ! -f demo-loading.html ]; then
  echo "demo-loading.html introuvable à la racine du repo."
  exit 1
fi
cp demo-loading.html index.html

# 2. Retirer l'IP en dur du contrat (MetalLB alloue librement)
python3 - <<'PY'
import re
p = "nkp-app.yaml"
s = open(p).read()
s = re.sub(r"^  ip: .*\n", "", s, flags=re.M)
open(p, "w").write(s)
PY

# 3. Régénérer les manifests (service sans loadBalancerIP)
.venv/bin/python .opencode/skills/nkp-deploy/render.py

# 4. Pousser via GitOps
git add index.html nkp-app.yaml k8s/
git commit -m "chore: RAZ demo -> page 'demo loading', IP LB dynamique"
git pull --rebase && git push

# 5. Attendre le déploiement puis remettre le WIP à idle
if [ -x .opencode/skills/nkp-deploy/check_deploy.sh ]; then
  .opencode/skills/nkp-deploy/check_deploy.sh verify || true
fi
IP=$(kubectl --context "${NKP_CONTEXT:-}" -n "${NKP_NAMESPACE:-}" get svc natatio \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
if [ -n "$IP" ]; then
  curl -s -m 10 -X POST "http://${IP}/demo-state" \
    -H 'X-Wip-Token: demo-wip-token' -H 'Content-Type: application/json' \
    -d '{"status":"idle","mode":"raz","message":"Démo en attente (page de chargement)","theme":"demo-loading"}' >/dev/null 2>&1 || true
fi

# 6. Aide
echo ""
echo "RAZ terminée. IP allouée : ${IP:-<voir kubectl>}"
echo "  kubectl --context \"\${NKP_CONTEXT:-}\" -n \"\${NKP_NAMESPACE:-}\" get svc natatio \\"
echo "    -o jsonpath='{.status.loadBalancer.ingress[0].ip}'"
echo ""
echo "Optionnel : supprimer l'ancienne app 'basket-jereme' si toujours présente :"
echo "  kubectl --context \"\${NKP_CONTEXT:-}\" -n \"\${NKP_NAMESPACE:-}\" delete svc,deploy basket-jereme --ignore-not-found"

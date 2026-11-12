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

TOKEN="${DEMO_STATE_TOKEN:-${WIP_TOKEN:-demo-wip-token}}"

# 5. Attendre le déploiement (l'etat raz est deduit de la page deployee au demarrage du pod)
if [ -x .opencode/skills/nkp-deploy/check_deploy.sh ]; then
  .opencode/skills/nkp-deploy/check_deploy.sh verify
fi

# Recuperer l'IP avec retries (MetalLB peut l'attribuer tardivement)
IP=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
  IP=$(kubectl --context "${NKP_CONTEXT:-}" -n "${NKP_NAMESPACE:-}" get svc natatio \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
  [ -n "$IP" ] && break
  sleep 3
done

# Remettre le dashboard en "en attente" (la verification ci-dessus a pu poster autre chose)
if [ -n "$IP" ]; then
  payload='{"status":"idle","mode":"raz","message":"Démo en attente (page de chargement)","theme":"demo-loading","pipeline":{"code":"pending","gitPush":"pending","ci":"pending","flux":"pending","rollout":"pending","health":"pending"}}'
  for _ in 1 2 3; do
    code=$(curl -s -m 10 -o /dev/null -w '%{http_code}' -X POST "http://${IP}/demo-state" \
      -H "X-Demo-State-Token: ${TOKEN}" -H 'Content-Type: application/json' \
      -d "$payload" 2>/dev/null || echo "000")
    [ "$code" = "200" ] && break
    echo "ATTENTION reset post_state HTTP $code (nouvelle tentative)" >&2
    sleep 2
  done
fi

# 6. Aide
echo ""
echo "RAZ terminée. IP allouée : ${IP:-<voir kubectl>}"
echo "  kubectl --context \"\${NKP_CONTEXT:-}\" -n \"\${NKP_NAMESPACE:-}\" get svc natatio \\"
echo "    -o jsonpath='{.status.loadBalancer.ingress[0].ip}'"
echo ""
echo "Optionnel : supprimer l'ancienne app 'basket-jereme' si toujours présente :"
echo "  kubectl --context \"\${NKP_CONTEXT:-}\" -n \"\${NKP_NAMESPACE:-}\" delete svc,deploy basket-jereme --ignore-not-found"

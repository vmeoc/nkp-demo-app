#!/usr/bin/env bash
# check_deploy.sh : dit à l'IA (et à l'humain) si le déploiement a réussi, et sinon pourquoi.
#
#   .github/skills/nkp-deploy/check_deploy.sh preflight   # avant le push : contrat + dry-run serveur
#   .github/skills/nkp-deploy/check_deploy.sh verify      # après le push : CI -> Flux -> pods
#
# Configuration : .nkp/target.env (non commité), par exemple :
#   NKP_CONTEXT=nkp-workload-admin@nkp-workload   # contexte kubectl du workload cluster
#   NKP_NAMESPACE=demo-vibe                        # namespace du Projet NKP
#   NKP_KUSTOMIZATION=                             # facultatif, détecté sinon
#
# La dernière ligne est toujours RESULT=<CODE>, lisible par l'IA :
#   OK | CONFIG_ERROR | PREFLIGHT_FAILED | CI_FAILED | FLUX_FAILED | FLUX_TIMEOUT | ROLLOUT_FAILED
# Compatible bash 3.2 (macOS).

set -uo pipefail

ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "Pas dans un repo Git"; echo "RESULT=CONFIG_ERROR"; exit 1; }
cd "$ROOT"
[ -f .nkp/target.env ] && { set -a; . .nkp/target.env; set +a; }

PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
RENDER=".github/skills/nkp-deploy/render.py"

fail() { echo "$2"; echo "RESULT=$1"; exit "${3:-1}"; }

[ -n "${NKP_NAMESPACE:-}" ] || fail CONFIG_ERROR "NKP_NAMESPACE manquant (fichier .nkp/target.env)."
command -v kubectl >/dev/null || fail CONFIG_ERROR "kubectl introuvable (brew install kubectl)."
K="kubectl -n $NKP_NAMESPACE"
[ -n "${NKP_CONTEXT:-}" ] && K="kubectl --context $NKP_CONTEXT -n $NKP_NAMESPACE"

APP=$(awk -F': *' '/^app:/{print $2; exit}' nkp-app.yaml 2>/dev/null | tr -d "\"' ")
[ -n "$APP" ] || fail CONFIG_ERROR "Champ app introuvable dans nkp-app.yaml."

diagnose_pods() {
  echo "--- Pods"
  $K get pods -l "app.kubernetes.io/name=$APP" -o wide 2>&1
  echo "--- Événements récents"
  $K get events --sort-by=.lastTimestamp 2>/dev/null | grep -i "$APP" | tail -n 15
  for pod in $($K get pods -l "app.kubernetes.io/name=$APP" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null); do
    echo "--- Logs $pod"
    $K logs "$pod" --all-containers --tail=30 2>&1 | tail -n 30
    $K logs "$pod" --all-containers --previous --tail=30 2>/dev/null | sed 's/^/[précédent] /' | tail -n 30
  done
}

preflight() {
  echo "== Contrat"
  $PY "$RENDER" --check || fail PREFLIGHT_FAILED "k8s/ pas à jour ou contrat invalide : lancer render.py." 6
  echo "== Dry-run côté serveur (admission, policies Gatekeeper/Kyverno, quotas)"
  out=$(kubectl ${NKP_CONTEXT:+--context "$NKP_CONTEXT"} apply -k k8s --dry-run=server -n "$NKP_NAMESPACE" 2>&1)
  rc=$?
  echo "$out"
  [ $rc -eq 0 ] || fail PREFLIGHT_FAILED "Le cluster refuserait ces manifests (voir message ci-dessus)." 6
  echo "RESULT=OK"
}

verify() {
  SRC_SHA=$(git rev-parse HEAD)
  BRANCH=$(git rev-parse --abbrev-ref HEAD)
  [ "$BRANCH" = "main" ] || echo "ATTENTION branche $BRANCH : Flux ne surveille que main."

  echo "== 1/3 CI GitHub Actions (commit ${SRC_SHA:0:7})"
  RUN_ID=""
  if command -v gh >/dev/null; then
    for _ in 1 2 3 4 5 6 7 8 9; do
      RUN_ID=$(gh run list --commit "$SRC_SHA" --workflow build-deploy.yml --limit 1 \
               --json databaseId -q '.[0].databaseId' 2>/dev/null)
      [ -n "$RUN_ID" ] && break
      sleep 5
    done
  else
    echo "ATTENTION gh introuvable : étape CI non vérifiée (brew install gh)."
  fi
  if [ -n "$RUN_ID" ]; then
    if ! gh run watch "$RUN_ID" --exit-status --interval 5 >/dev/null 2>&1; then
      echo "--- Logs des étapes en échec"
      gh run view "$RUN_ID" --log-failed 2>&1 | tail -n 60
      fail CI_FAILED "La CI a échoué : corriger le code ou le Dockerfile." 2
    fi
    echo "CI OK (run $RUN_ID)"
  else
    echo "Aucun build pour ce commit (changement de configuration seule) : on passe à Flux."
  fi

  git fetch -q origin "$BRANCH"
  TARGET=$(git rev-parse "origin/$BRANCH")
  echo "== 2/3 Flux NKP (révision attendue ${TARGET:0:7})"
  KS="${NKP_KUSTOMIZATION:-}"
  if [ -z "$KS" ]; then
    KS=$($K get kustomizations.kustomize.toolkit.fluxcd.io -o jsonpath='{.items[0].metadata.name}' 2>&1) \
      || fail CONFIG_ERROR "Impossible de lister les Kustomizations Flux : $KS"
    [ -n "$KS" ] || fail CONFIG_ERROR "Aucune Kustomization Flux dans $NKP_NAMESPACE : la source GitOps du Projet est-elle créée ?"
  fi
  SRC=$($K get kustomization.kustomize.toolkit.fluxcd.io "$KS" -o jsonpath='{.spec.sourceRef.name}' 2>/dev/null)
  now=$(date +%s)
  [ -n "$SRC" ] && $K annotate gitrepository.source.toolkit.fluxcd.io "$SRC" reconcile.fluxcd.io/requestedAt="$now" --overwrite >/dev/null 2>&1
  $K annotate kustomization.kustomize.toolkit.fluxcd.io "$KS" reconcile.fluxcd.io/requestedAt="$now" --overwrite >/dev/null 2>&1

  deadline=$(( $(date +%s) + 300 ))
  while :; do
    applied=$($K get kustomization.kustomize.toolkit.fluxcd.io "$KS" -o jsonpath='{.status.lastAppliedRevision}' 2>/dev/null)
    attempted=$($K get kustomization.kustomize.toolkit.fluxcd.io "$KS" -o jsonpath='{.status.lastAttemptedRevision}' 2>/dev/null)
    ready=$($K get kustomization.kustomize.toolkit.fluxcd.io "$KS" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
    msg=$($K get kustomization.kustomize.toolkit.fluxcd.io "$KS" -o jsonpath='{.status.conditions[?(@.type=="Ready")].message}' 2>/dev/null)
    case "$applied" in *"$TARGET"*) echo "Flux a appliqué la révision ${TARGET:0:7}"; break ;; esac
    case "$attempted" in *"$TARGET"*)
      [ "$ready" = "False" ] && fail FLUX_FAILED "Flux a refusé la révision : $msg" 3 ;;
    esac
    [ "$(date +%s)" -lt "$deadline" ] || fail FLUX_TIMEOUT "Révision non appliquée après 5 min. État Flux : $msg" 4
    sleep 10
  done

  echo "== 3/3 Rollout de deployment/$APP"
  deadline=$(( $(date +%s) + 180 ))
  while :; do
    if $K rollout status "deployment/$APP" --timeout=5s >/dev/null 2>&1; then break; fi
    reasons=$($K get pods -l "app.kubernetes.io/name=$APP" -o jsonpath='{range .items[*]}{range .status.initContainerStatuses[*]}{.state.waiting.reason}{"\n"}{end}{range .status.containerStatuses[*]}{.state.waiting.reason}{"\n"}{end}{end}' 2>/dev/null \
              | grep -E 'ImagePullBackOff|ErrImagePull|InvalidImageName|CrashLoopBackOff|CreateContainerConfigError' | sort -u | tr '\n' ' ')
    if [ -n "$reasons" ]; then diagnose_pods; fail ROLLOUT_FAILED "Pods en erreur : $reasons" 5; fi
    if [ "$(date +%s)" -ge "$deadline" ]; then diagnose_pods; fail ROLLOUT_FAILED "Rollout non terminé après 3 min." 5; fi
    sleep 5
  done

  echo "== Déploiement OK"
  $K get pods -l "app.kubernetes.io/name=$APP" 2>&1
  host=$($K get ingress "$APP" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null)
  ip=$($K get svc "$APP" -o jsonpath='{.status.loadBalancer.ingress[0].ip}{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
  [ -n "$host" ] && echo "URL : http://$host"
  [ -n "$ip" ] && echo "Adresse : http://$ip"
  echo "RESULT=OK"
}

case "${1:-}" in
  preflight) preflight ;;
  verify) verify ;;
  *) echo "Usage : $0 preflight|verify"; echo "RESULT=CONFIG_ERROR"; exit 1 ;;
esac

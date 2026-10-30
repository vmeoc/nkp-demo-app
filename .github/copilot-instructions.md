# Instructions du repo

Ce repo est déployé sur Nutanix Kubernetes Platform (NKP) en GitOps.

- Pour créer, déployer, modifier ou dépanner le déploiement, utilise le skill `nkp-deploy`.
- Ne modifie jamais les fichiers de `k8s/` à la main : ils sont générés depuis `nkp-app.yaml` (et `k8s/kustomization.yaml` appartient à la CI).
- Python : utilise `.venv/bin/python`.

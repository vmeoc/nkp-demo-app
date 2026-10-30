---
name: nkp-deploy
description: Crée, déploie et corrige l'application du repo sur Nutanix Kubernetes Platform (NKP) via GitOps. À utiliser dès que l'utilisateur veut créer une appli à héberger, la déployer, la mettre en ligne, changer d'environnement, de taille ou d'options (backup, tracing, exposition, LLM, expiration), ou comprendre pourquoi un déploiement NKP échoue.
---

# Déployer sur NKP

Tu ne rédiges jamais de manifest Kubernetes. Tu écris un **contrat d'intentions**, `nkp-app.yaml`, à la racine du repo. Le script `render.py` le traduit en manifests, la CI construit l'image, et Flux (intégré à NKP) déploie.

| Fichier | Qui l'écrit |
|---|---|
| code, `Dockerfile`, `nkp-app.yaml` | toi (avec l'accord de l'utilisateur) |
| `k8s/base/**` | uniquement `render.py` |
| `k8s/kustomization.yaml` | uniquement la CI (tag de l'image) |

## Règles impératives

- Ne modifie jamais un fichier de `k8s/` à la main. Pour changer le déploiement, change `nkp-app.yaml` puis relance `render.py`.
- Ne touche jamais `k8s/kustomization.yaml` : c'est le fichier de la CI. C'est ce qui évite les conflits Git.
- Utilise `.venv/bin/python` (à défaut `python3`) depuis la racine du repo.
- Ne contourne jamais une règle de la plateforme pour faire passer un déploiement : ne baisse pas l'environnement, ne retire pas une option obligatoire, ne désactive pas un contrôle. Explique la règle et propose une correction conforme.
- Ne commite jamais de secret. Pas de `git push --force`.
- Ne change jamais le champ `app` d'une appli déjà déployée sans prévenir l'utilisateur : cela crée une nouvelle appli.
- Parle à l'utilisateur dans sa langue.

## Étape 1 — Analyser le projet avant de poser une question

Lis le repo et déduis une proposition pour chaque option. Si `nkp-app.yaml` existe déjà, pars de ses valeurs.

| Signal dans le repo | Proposition |
|---|---|
| `requirements.txt`, `pyproject.toml` | `runtime: python` |
| `package.json` | `runtime: nodejs` |
| `pom.xml`, `build.gradle` | `runtime: java` |
| `*.csproj` | `runtime: dotnet` |
| uniquement HTML/CSS/JS servi par nginx | `runtime: static`, `tracing: false` |
| `EXPOSE` du Dockerfile, ou port dans le code (`app.run(port=…)`, `listen(…)`) | `port` |
| dépendances `openai`, `langchain`, `litellm`, `anthropic` | `llm: nai` |
| dépendances `psycopg`, `sqlalchemy`, `pymongo`, `mysql`, `redis` | signale qu'une base est requise ; seul `stateless` est supporté : demande comment procéder |
| nom de la branche ou du dossier contenant `prod`, `preprod`, `test` | `env` correspondant, sinon `dev` |
| `git config user.email` | `owner` = partie avant le `@`, en minuscules |
| nom du dossier du repo | `app` (minuscules, tirets) |
| prototype, démo, POC dans la demande | `expires` à 30 jours |

Valeurs par défaut sinon : `env: dev`, `archi: stateless`, `size: S`, `backup: none`, `tracing: true` (sauf `static`), `expose: {type: loadbalancer}`, `llm: none`.

Pour connaître toutes les valeurs autorisées et leur sens : `.venv/bin/python .github/skills/nkp-deploy/render.py --print-catalog`

## Étape 2 — Créer l'application si l'utilisateur le demande

- Par défaut : Python + Flask, une seule route, écoute sur `0.0.0.0:8080`, lancée par `python app.py`.
- `Dockerfile` basé sur `python:3.12-slim`, **pas alpine** : l'auto-instrumentation OpenTelemetry Python ne fonctionne pas avec musl.
- Le `Dockerfile` est à la racine du repo : c'est là que la CI le cherche.
- Code minimal : l'objectif est de montrer la plateforme, pas l'appli.

## Étape 3 — Proposer, puis faire valider en une seule fois

Présente un tableau unique, puis pose **une seule** question. Ne pose pas les questions une par une.

Exemple :

| Option | Proposition | Pourquoi |
|---|---|---|
| Nom | `hello-nkp` | nom du dossier |
| Environnement | `dev` | branche `main`, pas d'indication contraire |
| Architecture | `stateless` | aucune base de données détectée |
| Taille | `S` | appli de démonstration |
| Sauvegarde | `none` | stateless : Git suffit |
| Tracing | activé | Python, auto-instrumentable |
| Exposition | IP externe | accès direct pour la démo |
| Accès LLM | aucun | pas de client LLM dans les dépendances |
| Expiration | 2026-12-31 | prototype |

> Je valide ces choix ? Tu peux en changer autant que tu veux en une phrase, par exemple « env prod, backup daily, pas d'expiration ».

Si l'utilisateur a dit de ne pas lui poser de question, applique la proposition et signale-le en une ligne.

## Étape 4 — Écrire le contrat et générer

1. Écris `nkp-app.yaml` (voir le modèle ci-dessous).
2. Lance `.venv/bin/python .github/skills/nkp-deploy/render.py`.
3. En cas d'`ERREUR`, le message dit quoi corriger : corrige `nkp-app.yaml` (ou demande à l'utilisateur si le choix lui appartient, par exemple un centre de coût) et relance.
4. Montre à l'utilisateur le résumé affiché par le script et les lignes `ATTENTION`.

```yaml
app: hello-nkp
owner: vincent
env: dev
archi: stateless
runtime: python
port: 8080
size: S
backup: none
tracing: true
expose:
  type: loadbalancer
llm: none
expires: 2026-12-31
```

## Étape 5 — Pré-vol (recommandé)

`.github/skills/nkp-deploy/check_deploy.sh preflight`

Le script envoie les manifests au cluster en `--dry-run=server` : les politiques de la plateforme (Gatekeeper, Kyverno, quotas) répondent **avant** le push. Si `RESULT=PREFLIGHT_FAILED`, lis le message de refus, corrige le contrat, régénère, recommence. Si `RESULT=CONFIG_ERROR`, signale-le à l'utilisateur et continue sans pré-vol.

## Étape 6 — Pousser

```bash
git add -A
git commit -m "<résumé du changement>"
git pull --rebase
git push
```

## Étape 7 — Vérifier, et corriger si besoin

Lance `.github/skills/nkp-deploy/check_deploy.sh verify` (jusqu'à 8 minutes). Lis la dernière ligne `RESULT=…` et les messages au-dessus.

| RESULT | Cause typique | Action |
|---|---|---|
| `OK` | | Donne l'URL ou l'adresse à l'utilisateur. Puis `git pull --rebase` pour récupérer le commit de la CI. |
| `CI_FAILED` | build Docker cassé, dépendance manquante | Corrige le code ou le `Dockerfile` d'après le log. |
| `FLUX_FAILED`, message `admission webhook … denied` | règle de la plateforme | Corrige le contrat pour respecter la règle (replicas, taille…). Jamais l'inverse. |
| `FLUX_FAILED`, message `field is immutable` | sélecteur changé sur un Deployment existant | Arrête-toi et explique : il faut supprimer l'ancien Deployment ou changer `app`. |
| `ROLLOUT_FAILED`, `CrashLoopBackOff` | l'appli plante au démarrage | Lis les logs, corrige le code, vérifie que `port` correspond au port réellement écouté. |
| `ROLLOUT_FAILED`, `ImagePullBackOff` | package GHCR privé, ou build pas terminé | Problème de plateforme : explique à l'utilisateur comment rendre le package public. |
| `ROLLOUT_FAILED`, `CreateContainerConfigError` | secret `nai-credentials` absent | Problème de plateforme : demande de créer le secret dans le Projet NKP. |
| `ROLLOUT_FAILED`, pods `Pending` | quota du Projet ou capacité | Propose une taille inférieure, ou demande un quota plus élevé. |
| `FLUX_TIMEOUT` | source GitOps non prête, mauvais chemin | Problème de plateforme : explique et donne l'état Flux affiché. |
| `CONFIG_ERROR` | outillage local | Explique ce qui manque (kubectl, gh, `.nkp/target.env`). |

Boucle de correction :
- Après une correction de ta part : étapes 4 à 7 à nouveau.
- **Trois tentatives au maximum.** Ensuite, arrête et résume à l'utilisateur ce qui a été essayé et ce qui bloque.
- Si la cause relève de la plateforme (secret, quota, accès, réseau), ne tente rien : explique et donne la commande ou l'écran NKP concerné.
- À chaque correction, dis en une ligne ce que tu as changé et pourquoi.

## Ce que fait chaque option sur NKP

| Option | Traduction |
|---|---|
| `env` | label `nkp.demo/env`, replicas par défaut, règles prod (2 replicas, centre de coût, pas d'expiration) |
| `size` | requests et limits CPU/mémoire, cadrés par les quotas du Projet |
| `backup` | label `nkp.demo/backup` (simulé : aucune politique Velero n'est créée dans la démo) |
| `tracing` | annotation `instrumentation.opentelemetry.io/inject-<langage>` lue par l'opérateur OpenTelemetry |
| `expose` | Service ClusterIP ou LoadBalancer, ou Ingress avec nom d'hôte |
| `llm: nai` | `envFrom` du secret `nai-credentials` (NAI_BASE_URL, NAI_API_KEY, NAI_MODEL) |
| `expires` | label `nkp.demo/expires` lu par un job de nettoyage côté plateforme |
| `owner`, `cost_center` | labels pour la gouvernance et le reporting des coûts |

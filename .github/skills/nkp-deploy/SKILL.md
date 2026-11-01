---
name: nkp-deploy
description: Le but de ce skill est de participer à une démo client afin de montrer comment une applicaiton vibecoder peut tirer parti des caractéristiques d'une plateformes Kubernetes (Nutanix Kubernets Platform) pour être correctement dépployé. Le développeur va demander à modifier le fichier index.html en faisant une modification simple. Tu vas procéder à cette modification le plus rapidement et le plus simplement possible car le but de la démo est de demander aux développeur de valider le "contrat d'intention" nkp contenant les caractéristiques de l'application pour être correctemetn déployée par NKP. Ton job est donc de modifier et déployer l'application du repo sur Nutanix Kubernetes Platform (NKP) via GitOps. Ce skills est à utiliser dès que l'utilisateur veut créer ou modifier une appli à héberger, la déployer, la mettre en ligne, changer d'environnement, de taille ou d'options (backup, tracing, exposition, LLM, expiration), ou comprendre pourquoi un déploiement NKP échoue.
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
- RÈGLE BLOQUANTE : aucune création ou modification de `nkp-app.yaml`, aucun `render.py`, aucun `git add/commit/push`, et aucun déploiement NKP ne doivent être lancés sans approbation explicite du développeur.
- Avant toute écriture du contrat, présente le tableau complet des valeurs exactes proposées et attend une réponse affirmative claire du type « je valide » ou « oui, je valide ». Sans réponse explicite, tu ne touches ni `nkp-app.yaml`, ni les manifests générés, et tu ne pousses rien.
- Avant chaque push de déploiement, même si le contrat n'a pas besoin de changer pour cette livraison, présente aussi les valeurs exactes de `nkp-app.yaml` qui seront poussées et demande leur approbation explicite. Cette confirmation est impérative, sans exception : ni des valeurs par défaut, ni une demande de ne pas poser de questions, ni une approbation antérieure ne la remplacent.
- Ne contourne jamais une règle de la plateforme pour faire passer un déploiement : ne baisse pas l'environnement, ne retire pas une option obligatoire, ne désactive pas un contrôle. Explique la règle et propose une correction conforme.
- Ne commite jamais de secret. Pas de `git push --force`.
- Ne change jamais le champ `app` d'une appli déjà déployée sans prévenir l'utilisateur : cela crée une nouvelle appli.
- Parle à l'utilisateur dans sa langue.
- la démo est faite pour montrer un déploiement sur NKP donc même si l'utilisateur ne le demande pas, déploie sur NKP

## Étape 1 — Analyser le projet avant de poser une question

Lis les fichiers locaux. Ne lis pas l'historique git. Déduis une proposition pour chaque option. Si `nkp-app.yaml` existe déjà, pars de ses valeurs.

Montre ce texte au développer en tant que résumé des informations que tu vas chercher à définir pour que le projet puisse bien être déployé.
app : Nom de l'application [string] - Nom DNS : minuscules, chiffres et tirets, 40 caractères max. Devient le nom du Deployment et du Service. Ne plus le changer une fois déployé.
owner : Propriétaire [string] - Identifiant de la personne ou de l'équipe responsable (label Kubernetes).
cost_center (facultatif) : Centre de coût [string] - Obligatoire en prod. Sert au reporting des coûts.
env : Environnement
    dev (Développement) - Règles souples, 1 replica par défaut.
    test (Test) - Recette fonctionnelle, 1 replica par défaut.
    preprod (Pré-production) - Iso-prod, 2 replicas par défaut.
    prod (Production) - 2 replicas minimum, centre de coût obligatoire, pas de date d'expiration.
archi : Type d'architecture
    stateless (Stateless) - Pods sans volume persistant. Seul type supporté dans la démo.
    backend-db (Backend + nouvelle base) - Base de données provisionnée par la plateforme. Pas encore supporté.
    backend-db-existing (Backend + base existante) - Connexion à une base existante. Pas encore supporté.
runtime : Langage
    python (Python)
    nodejs (Node.js)
    java (Java)
    dotnet (.NET)
    static (Site statique (nginx)) - Pas de tracing possible.
port : Port d'écoute du conteneur [integer]
replicas (facultatif) : Nombre de replicas [integer] - Facultatif. Par défaut : 1 en dev/test, 2 en preprod/prod.
size : Taille
    S (Small) - 0,1 CPU / 128 Mi demandés, plafond 0,5 CPU / 256 Mi.
    M (Medium) - 0,25 CPU / 256 Mi demandés, plafond 1 CPU / 512 Mi.
    L (Large) - 0,5 CPU / 512 Mi demandés, plafond 2 CPU / 1 Gi.
backup : Sauvegarde
    none (Aucune) - Git suffit pour une appli stateless.
    daily (Quotidienne) - 02:00, rétention 7 jours.
    hourly (Horaire) - Toutes les heures, rétention 48 heures.
tracing : Tracing distribué [boolean] - true = auto-instrumentation OpenTelemetry injectée par l'opérateur, sans modifier le code.
expose : Exposition
    type : 
        none (Interne au cluster) - Service ClusterIP uniquement.
        loadbalancer (Adresse IP) - Service LoadBalancer (MetalLB ou équivalent requis).
        ingress (URL) - Ingress avec un nom d'hôte.
    host : Nom d'hôte [string]
    ingress_class : Classe d'ingress [string] - Par défaut kommander-traefik. Vérifier avec : kubectl get ingressclass
llm (facultatif) : Accès LLM
    none (Aucun)
    nai (Nutanix Enterprise AI) - Injecte le secret nai-credentials (NAI_BASE_URL, NAI_API_KEY, NAI_MODEL) dans le conteneur.
expires (facultatif) : Date d'expiration [string] - Facultatif, format AAAA-MM-JJ. Interdit en prod. Posé en label ; la suppression est faite par un job planifié côté plateforme.

Il est important qu'il voit ce degré de connaissance que tu as du projet et la direction dans laquelle tu veux aller. 

## Étape 2 — Modifier l'application si l'utilisateur le demande

- Le développeur te demandera généralement juste de modifier le texte affichant Hello world en hello <ça dépendra>. Fais cette modif dans index.html, ne cherche pas à vérifier ton résultat. Passe à l'étape suivante.
- Code minimal : l'objectif est de montrer la plateforme, pas l'appli.

## Étape 3 — Présenter le contrat et attendre la validation explicite

Avant toute création ou modification de `nkp-app.yaml`, présente un tableau unique avec les valeurs proposées et attends l'accord explicite de l'utilisateur avant d'écrire. Avant chaque push de déploiement, présente aussi les valeurs exactes du contrat qui seront poussées et demande leur approbation, même si le contrat n'a pas besoin de changer pour cette livraison. Ne pose pas les questions une par une : demande une confirmation globale. Sans réponse affirmative explicite, ne crée ni ne modifie le contrat et ne pousse pas le déploiement. Cette étape est un blocage obligatoire : ne pas faire cette étape = interdiction de continuer.
Crée nkp-app.yaml s'il n'est pas présent, ou modifie le s'il existe déjà.

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

## Étape 4 — Écrire le contrat et générer

1. Après confirmation, écris `nkp-app.yaml` seulement si ses valeurs doivent changer. Si le contrat existant est déjà conforme et approuvé, laisse-le inchangé.
2. Après toute création ou modification de `nkp-app.yaml`, lance `.venv/bin/python .github/skills/nkp-deploy/render.py`.
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

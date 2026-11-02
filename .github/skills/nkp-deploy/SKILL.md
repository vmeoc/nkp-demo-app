---
name: nkp-deploy
description: Modifier et déployer cette application sur Nutanix Kubernetes Platform via GitOps. Par défaut, utiliser la MCP App open_nkp_contract_form dans le chat VS Code pour faire examiner et confirmer le contrat d'intentions NKP ; cette confirmation autorise son application, le push et le déploiement, sans confirmation supplémentaire. N'utiliser le questionnaire texte qu'en solution de repli si l'interface MCP est indisponible. Utiliser ce skill pour les demandes de création, modification, hébergement, déploiement ou dépannage NKP.
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
- La confirmation explicite du contrat dans le formulaire MCP vaut approbation pour appliquer exactement les valeurs confirmées, générer les manifests, pousser les changements nécessaires et déployer sur NKP. Ne demande pas une seconde confirmation avant le push ou le déploiement.
- Si le formulaire MCP est indisponible, le parcours texte doit présenter le contrat exact et demander une seule approbation explicite qui couvre son application et le déploiement. N'interprète jamais une erreur ou une absence de réponse comme une approbation.
- Si une correction après validation change une valeur du contrat, arrête-toi et fais confirmer le nouveau contrat dans le formulaire avant de l'appliquer et de poursuivre. Une correction de code ou une régénération sans changement de contrat ne nécessite pas de nouvelle confirmation.
- Ne contourne jamais une règle de la plateforme pour faire passer un déploiement : ne baisse pas l'environnement, ne retire pas une option obligatoire, ne désactive pas un contrôle. Explique la règle et propose une correction conforme.
- Ne commite jamais de secret. Pas de `git push --force`.
- Ne change jamais le champ `app` d'une appli déjà déployée sans prévenir l'utilisateur : cela crée une nouvelle appli.
- Parle à l'utilisateur dans sa langue.
- la démo est faite pour montrer un déploiement sur NKP donc même si l'utilisateur ne le demande pas, déploie sur NKP

## Étape 1 — Analyser le projet et ouvrir le formulaire graphique

Lis les fichiers locaux. Ne lis pas l'historique git. Déduis une proposition pour chaque option. Si `nkp-app.yaml` existe déjà, pars de ses valeurs.

**Par défaut, utilise le formulaire MCP App dans le chat VS Code** pour présenter et faire choisir le contrat : appelle l'outil MCP `open_nkp_contract_form` du serveur `nkp-contract`. Il préremplit le contrat existant, explique les options et valide les choix selon le schéma et les règles de la plateforme. L'utilisateur doit examiner l'aperçu complet du contrat puis confirmer dans le formulaire. Cette confirmation est l'approbation pour appliquer le contrat et procéder au déploiement ; ne demande pas une confirmation distincte avant le push.

Si l'outil MCP n'est pas disponible, si l'interface ne s'affiche pas ou si son chargement échoue, utilise le parcours de repli dans le chat : présente le tableau complet des options et valeurs proposées, puis attends une validation affirmative explicite. N'interprète jamais une erreur ou une absence de réponse comme une approbation.

La confirmation du formulaire autorise l'application des valeurs affichées et le déploiement. Si l'interface est indisponible, obtiens dans le parcours texte une approbation explicite unique couvrant le contrat exact et sa livraison. Ne redemande pas l'approbation avant le push. Si le contrat doit changer après confirmation, fais confirmer la nouvelle proposition avant de continuer.

Le formulaire graphique présente les options ci-dessous à l'utilisateur avec leurs descriptions. En solution de repli uniquement, montre ce catalogue dans le chat pour expliquer les choix disponibles.
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

## Étape 3 — Faire examiner le contrat et obtenir l'approbation

Parcours normal : dans le formulaire MCP App, fais afficher les valeurs actuelles, les choix et leurs explications, les erreurs/avertissements de validation et l'aperçu du contrat exact. La confirmation explicite dans le formulaire vaut à la fois approbation pour créer ou modifier `nkp-app.yaml` et approbation pour pousser et déployer ces valeurs. Après cette confirmation, poursuis sans nouvelle demande d'approbation.

Parcours de repli uniquement si l'interface MCP App est indisponible : présente un tableau unique avec les valeurs proposées et demande une réponse affirmative claire qui autorise leur application et le déploiement. Ne pose pas les questions une par une. Sans approbation explicite, ne crée ni ne modifie le contrat et ne pousse rien. Cette étape est bloquante.

Après l'approbation, crée `nkp-app.yaml` s'il n'est pas présent, ou modifie-le s'il existe déjà. Ne redemande pas une approbation avant le push lorsque les valeurs n'ont pas changé depuis le formulaire. Si une contrainte du cluster oblige à changer le contrat, soumets la nouvelle proposition au formulaire et attends sa confirmation.

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

## Étape 6 — Pousser après l'approbation du formulaire

```bash
git add <fichiers liés à la modification et au déploiement>
git commit -m "<résumé du changement>"
git pull --rebase
git push
```

N'utilise pas `git add -A` : le worktree peut contenir des changements sans rapport, des fichiers locaux de configuration ou des sauvegardes. N'inclus que les fichiers nécessaires à la demande approuvée. La confirmation du formulaire autorise ce push ; aucune confirmation supplémentaire n'est requise.

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

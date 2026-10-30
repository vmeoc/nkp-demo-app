#!/usr/bin/env python3
"""render.py : traduit le contrat nkp-app.yaml en manifests Kubernetes.

A lancer depuis la racine du repo :
  .venv/bin/python .github/skills/nkp-deploy/render.py                  # génère k8s/
  .venv/bin/python .github/skills/nkp-deploy/render.py --check          # k8s/base est-il à jour ?
  .venv/bin/python .github/skills/nkp-deploy/render.py --print-catalog  # options autorisées

Propriété des fichiers (c'est ce qui évite les conflits Git) :
  nkp-app.yaml            -> écrit par le développeur ou l'IA
  k8s/base/**             -> écrit UNIQUEMENT par ce script
  k8s/kustomization.yaml  -> créé une seule fois par ce script, ensuite modifié UNIQUEMENT par la CI

Codes de sortie : 0 = OK, 1 = contrat invalide, 2 = k8s/base pas à jour (--check).
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("Dépendances manquantes. Lancer : .venv/bin/pip install pyyaml jsonschema")

SKILL_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = SKILL_DIR / "schema.json"
CONTRACT = Path("nkp-app.yaml")
K8S = Path("k8s")
BASE = K8S / "base"
TOP_KUSTOMIZATION = K8S / "kustomization.yaml"

IMAGE_PLACEHOLDER = "app-image"  # nom logique, remplacé par la CI via kustomization.yaml
P = "nkp.demo"                   # préfixe des labels de la plateforme de démo
HEADER = "# GÉNÉRÉ par render.py depuis nkp-app.yaml. Ne pas modifier à la main.\n"

SIZES = {
    "S": {"requests": {"cpu": "100m", "memory": "128Mi"}, "limits": {"cpu": "500m", "memory": "256Mi"}},
    "M": {"requests": {"cpu": "250m", "memory": "256Mi"}, "limits": {"cpu": "1", "memory": "512Mi"}},
    "L": {"requests": {"cpu": "500m", "memory": "512Mi"}, "limits": {"cpu": "2", "memory": "1Gi"}},
}
DEFAULT_REPLICAS = {"dev": 1, "test": 1, "preprod": 2, "prod": 2}
BACKUP_POLICY = {
    "none": "aucune sauvegarde",
    "daily": "quotidienne 02:00, rétention 7 jours (simulé)",
    "hourly": "horaire, rétention 48 heures (simulé)",
}
OTEL_LANG = {"python": "python", "nodejs": "nodejs", "java": "java", "dotnet": "dotnet"}
DEFAULT_INGRESS_CLASS = "kommander-traefik"


class ContractError(Exception):
    pass


class NoAliasDumper(yaml.SafeDumper):
    """Pas d'ancres &id001 / *id001 : des manifests lisibles par un humain."""
    def ignore_aliases(self, data):
        return True


# ---------- lecture et validation ----------

def _stringify_dates(node):
    """PyYAML lit 2026-12-31 comme une date : on la remet en chaîne pour le schéma."""
    if isinstance(node, dict):
        return {k: _stringify_dates(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_stringify_dates(v) for v in node]
    if isinstance(node, (dt.date, dt.datetime)):
        return node.isoformat()[:10]
    return node


def load_schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def load_contract():
    if not CONTRACT.exists():
        raise ContractError(f"{CONTRACT} introuvable à la racine du repo.")
    data = yaml.safe_load(CONTRACT.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ContractError(f"{CONTRACT} doit contenir un objet YAML (clé: valeur).")
    return _stringify_dates(data)


def _allowed_values(subschemas):
    if subschemas and all("const" in s for s in subschemas):
        return [s["const"] for s in subschemas]
    return None


def validate_schema(contract, schema):
    errors = []
    for e in sorted(Draft202012Validator(schema).iter_errors(contract), key=lambda e: list(e.absolute_path)):
        where = ".".join(str(p) for p in e.absolute_path) or "(racine)"
        allowed = _allowed_values(e.schema.get("oneOf")) if e.validator == "oneOf" else None
        if e.validator == "required":
            missing = e.message.split("'")[1] if "'" in e.message else e.message
            errors.append(f"{where} : champ obligatoire manquant : {missing}")
        elif allowed:
            errors.append(f"{where} : {e.instance!r} non autorisé. Valeurs possibles : {', '.join(map(str, allowed))}")
        else:
            errors.append(f"{where} : {e.message}")
    return errors


def check_rules(c):
    """Règles de la plateforme, avec des messages que l'IA peut exploiter pour se corriger."""
    errors, warnings = [], []
    replicas = c.get("replicas", DEFAULT_REPLICAS[c["env"]])

    if c["archi"] != "stateless":
        errors.append(f"archi : '{c['archi']}' n'est pas encore supporté par la plateforme de démo. Utiliser 'stateless'.")

    if c["env"] == "prod":
        if replicas < 2:
            errors.append("replicas : la prod exige au moins 2 replicas (haute disponibilité).")
        if not c.get("cost_center"):
            errors.append("cost_center : obligatoire en prod.")
        if c.get("expires"):
            errors.append("expires : une application de prod ne peut pas avoir de date d'expiration.")
        if c["backup"] == "none":
            warnings.append("backup : une application de prod sans sauvegarde est déconseillée.")

    if c["tracing"] and c["runtime"] == "static":
        errors.append("tracing : l'auto-instrumentation OpenTelemetry ne s'applique pas à un site statique. "
                      "Passer tracing à false ou utiliser un runtime python, nodejs, java ou dotnet.")

    if c.get("expires"):
        try:
            if dt.date.fromisoformat(c["expires"]) <= dt.date.today():
                errors.append(f"expires : {c['expires']} est déjà passé.")
        except ValueError:
            errors.append(f"expires : {c['expires']} n'est pas une date valide.")

    if c.get("llm") == "nai":
        warnings.append("llm : le secret 'nai-credentials' doit exister dans le namespace du Projet "
                        "(NKP > Projet > Secrets). Sinon le pod restera en CreateContainerConfigError.")
    if c["tracing"]:
        warnings.append("tracing : nécessite l'opérateur OpenTelemetry et une ressource Instrumentation "
                        "dans le namespace du Projet.")
    return replicas, errors, warnings


# ---------- génération ----------

def build_labels(c):
    labels = {
        "app.kubernetes.io/name": c["app"],
        "app.kubernetes.io/managed-by": "nkp-deploy",
        f"{P}/env": c["env"],
        f"{P}/owner": c["owner"],
        f"{P}/archi": c["archi"],
        f"{P}/backup": c["backup"],
        f"{P}/tracing": "enabled" if c["tracing"] else "disabled",
        f"{P}/llm": c.get("llm", "none"),
    }
    if c.get("cost_center"):
        labels[f"{P}/cost-center"] = c["cost_center"]
    if c.get("expires"):
        labels[f"{P}/expires"] = c["expires"]
    return labels


def build_manifests(c, replicas):
    app = c["app"]
    labels = build_labels(c)
    selector = {"app.kubernetes.io/name": app}  # ne jamais y ajouter env, owner... (selector immuable)

    pod_annotations = {}
    env_vars = [{"name": "APP_ENV", "value": c["env"]}]
    if c["tracing"]:
        pod_annotations[f"instrumentation.opentelemetry.io/inject-{OTEL_LANG[c['runtime']]}"] = "true"
        env_vars.append({"name": "OTEL_SERVICE_NAME", "value": app})

    container = {
        "name": app,
        "image": IMAGE_PLACEHOLDER,
        "ports": [{"name": "http", "containerPort": c["port"]}],
        "env": env_vars,
        "resources": SIZES[c["size"]],
        "readinessProbe": {"tcpSocket": {"port": "http"}, "initialDelaySeconds": 3, "periodSeconds": 5},
        "livenessProbe": {"tcpSocket": {"port": "http"}, "initialDelaySeconds": 15, "periodSeconds": 10},
    }
    if c.get("llm") == "nai":
        container["envFrom"] = [{"secretRef": {"name": "nai-credentials"}}]

    template_meta = {"labels": labels}
    if pod_annotations:
        template_meta["annotations"] = pod_annotations

    files = {}
    files["deployment.yaml"] = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": app,
            "labels": labels,
            "annotations": {f"{P}/backup-policy": BACKUP_POLICY[c["backup"]]},
        },
        "spec": {
            "replicas": replicas,
            "revisionHistoryLimit": 3,
            "selector": {"matchLabels": selector},
            "template": {"metadata": template_meta, "spec": {"containers": [container]}},
        },
    }

    expose = c["expose"]
    files["service.yaml"] = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": app, "labels": labels},
        "spec": {
            "type": "LoadBalancer" if expose["type"] == "loadbalancer" else "ClusterIP",
            "selector": selector,
            "ports": [{"name": "http", "port": 80, "targetPort": "http"}],
        },
    }

    if expose["type"] == "ingress":
        files["ingress.yaml"] = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {"name": app, "labels": labels},
            "spec": {
                "ingressClassName": expose.get("ingress_class", DEFAULT_INGRESS_CLASS),
                "rules": [{
                    "host": expose["host"],
                    "http": {"paths": [{
                        "path": "/",
                        "pathType": "Prefix",
                        "backend": {"service": {"name": app, "port": {"name": "http"}}},
                    }]},
                }],
            },
        }

    files["kustomization.yaml"] = {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization",
        "resources": sorted(f for f in files if f != "kustomization.yaml"),
    }
    return {name: HEADER + yaml.dump(doc, Dumper=NoAliasDumper, sort_keys=False, allow_unicode=True) for name, doc in files.items()}


def guess_image_name():
    try:
        url = subprocess.run(["git", "remote", "get-url", "origin"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "ghcr.io/OWNER/REPO"
    m = re.search(r"github\.com[:/]([^/]+)/(.+?)(?:\.git)?/?$", url)
    return f"ghcr.io/{m.group(1).lower()}/{m.group(2).lower()}" if m else "ghcr.io/OWNER/REPO"


def top_kustomization():
    return (
        "# Fichier géré par la CI : seules les lignes newName et newTag changent à chaque build.\n"
        "# Ne pas modifier à la main, ni le régénérer : c'est ce qui évite les conflits Git.\n"
        "apiVersion: kustomize.config.k8s.io/v1beta1\n"
        "kind: Kustomization\n"
        "resources:\n"
        "  - base\n"
        "images:\n"
        f"  - name: {IMAGE_PLACEHOLDER}\n"
        f"    newName: {guess_image_name()}\n"
        '    newTag: "bootstrap"\n'
    )


# ---------- sorties ----------

def summary(c, replicas, files):
    expose = c["expose"]
    if expose["type"] == "ingress":
        acces = f"http://{expose['host']} (Ingress, classe {expose.get('ingress_class', DEFAULT_INGRESS_CLASS)})"
    elif expose["type"] == "loadbalancer":
        acces = "IP externe du Service LoadBalancer"
    else:
        acces = "interne au cluster (ClusterIP)"
    lines = [
        f"Application  : {c['app']} ({c['runtime']}, port {c['port']}, archi {c['archi']})",
        f"Environnement: {c['env']} -> {replicas} replica(s), taille {c['size']}",
        f"Sauvegarde   : {BACKUP_POLICY[c['backup']]} -> label {P}/backup={c['backup']}",
        "Tracing      : " + (f"auto-instrumentation OTel {OTEL_LANG[c['runtime']]}" if c["tracing"] else "désactivé"),
        f"Accès LLM    : {c.get('llm', 'none')}",
        f"Exposition   : {acces}",
        f"Expiration   : {c.get('expires') or 'aucune'}",
        f"Fichiers     : " + ", ".join(f"k8s/base/{f}" for f in sorted(files)),
    ]
    return "\n".join(lines)


def print_catalog(schema):
    def describe(name, prop, indent=""):
        title = prop.get("title", "")
        allowed = prop.get("oneOf")
        if allowed and all("const" in s for s in allowed):
            print(f"{indent}{name} : {title}")
            for s in allowed:
                desc = f" - {s['description']}" if s.get("description") else ""
                print(f"{indent}    {s['const']} ({s.get('title', '')}){desc}")
        elif prop.get("type") == "object":
            print(f"{indent}{name} : {title}")
            for sub, sp in prop.get("properties", {}).items():
                describe(sub, sp, indent + "    ")
        else:
            desc = f" - {prop['description']}" if prop.get("description") else ""
            print(f"{indent}{name} : {title} [{prop.get('type', '?')}]{desc}")

    required = set(schema.get("required", []))
    for name, prop in schema["properties"].items():
        describe(name + ("" if name in required else " (facultatif)"), prop)


def main():
    parser = argparse.ArgumentParser(description="nkp-app.yaml -> k8s/")
    parser.add_argument("--check", action="store_true", help="vérifie que k8s/base correspond au contrat, sans écrire")
    parser.add_argument("--print-catalog", action="store_true", help="affiche les options autorisées")
    args = parser.parse_args()

    schema = load_schema()
    if args.print_catalog:
        print_catalog(schema)
        return 0

    try:
        contract = load_contract()
    except ContractError as e:
        print(f"ERREUR {e}", file=sys.stderr)
        return 1

    errors = validate_schema(contract, schema)
    if errors:
        print("ERREUR contrat invalide (nkp-app.yaml) :", file=sys.stderr)
        print("\n".join(f"  - {e}" for e in errors), file=sys.stderr)
        return 1

    replicas, errors, warnings = check_rules(contract)
    if errors:
        print("ERREUR règles de la plateforme non respectées :", file=sys.stderr)
        print("\n".join(f"  - {e}" for e in errors), file=sys.stderr)
        return 1

    files = build_manifests(contract, replicas)

    if args.check:
        on_disk = {p.name: p.read_text(encoding="utf-8") for p in BASE.glob("*.yaml")} if BASE.exists() else {}
        if on_disk != files or not TOP_KUSTOMIZATION.exists():
            print("ERREUR k8s/ n'est pas à jour : relancer render.py puis committer.", file=sys.stderr)
            return 2
        print("OK k8s/base est à jour.")
        return 0

    BASE.mkdir(parents=True, exist_ok=True)
    for stale in BASE.glob("*.yaml"):
        if stale.name not in files:
            stale.unlink()
    for name, content in files.items():
        (BASE / name).write_text(content, encoding="utf-8")
    created_top = False
    if not TOP_KUSTOMIZATION.exists():
        TOP_KUSTOMIZATION.write_text(top_kustomization(), encoding="utf-8")
        created_top = True

    print("OK manifests générés.")
    print(summary(contract, replicas, files))
    if created_top:
        print(f"Créé : {TOP_KUSTOMIZATION} (géré ensuite par la CI)")
    for w in warnings:
        print(f"ATTENTION {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

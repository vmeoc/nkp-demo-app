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
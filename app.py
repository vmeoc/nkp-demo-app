import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

APP_VERSION = os.environ.get("APP_VERSION", "dev")
DEMO_STATE_TOKEN = os.environ.get("DEMO_STATE_TOKEN", os.environ.get("WIP_TOKEN", "demo-wip-token"))
WIP_TOKEN = DEMO_STATE_TOKEN  # compatibilite avec l'ancien nom

# Stockage ephemere en memoire (suffisant pour une demo de quelques minutes).
_DEMO_STATE = {"status": "idle", "mode": "idle", "message": "", "theme": "", "started": "", "updated": ""}


def _init_demo_state_from_index():
    """Deduit l'etat initial de la demo depuis la page deployee (index.html).

    Cela rend l'etat persistant a travers les redemarrages de pod : la page
    'demo loading' embarque un marqueur demo-state=raz, une page de theme
    normale laisse l'etat a idle.
    """
    global _DEMO_STATE
    try:
        path = os.path.join(os.path.dirname(__file__), "index.html")
        with open(path, encoding="utf-8") as f:
            html = f.read()
    except OSError:
        return
    if 'name="demo-state" content="raz"' in html or "name='demo-state' content='raz'" in html:
        now = datetime.now(timezone.utc).isoformat()
        _DEMO_STATE = {
            "status": "idle",
            "mode": "raz",
            "message": "Démo en attente (page de chargement)",
            "theme": "demo-loading",
            "started": "",
            "updated": now,
        }


_init_demo_state_from_index()


def _demo_state_response():
    return jsonify(_DEMO_STATE)


@app.get("/")
def hello():
    return send_file(os.path.join(os.path.dirname(__file__), "index.html"))


@app.get("/healthz")
def healthz():
    return jsonify(status="ok", version=APP_VERSION, app="natatio")


@app.get("/status")
def status():
    return send_file(os.path.join(os.path.dirname(__file__), "status.html"))


@app.get("/demo-state")
@app.get("/wip-status")  # alias de compatibilite (deprecie)
def demo_state_get():
    return _demo_state_response()


@app.post("/demo-state")
@app.post("/wip-status")  # alias de compatibilite (deprecie)
def demo_state_post():
    token = request.headers.get("X-Wip-Token", "") or request.headers.get("X-Demo-State-Token", "")
    if token != DEMO_STATE_TOKEN:
        return jsonify(error="unauthorized"), 401
    data = request.get_json(silent=True) or {}
    now = datetime.now(timezone.utc).isoformat()
    status_val = data.get("status", "idle")
    if status_val not in ("idle", "in-progress", "deploying"):
        return jsonify(error="invalid status"), 400
    mode_val = data.get("mode")
    if mode_val is None:
        mode_val = "demo" if status_val in ("in-progress", "deploying") else "idle"
    if mode_val not in ("idle", "demo", "raz"):
        return jsonify(error="invalid mode"), 400
    _DEMO_STATE["status"] = status_val
    _DEMO_STATE["mode"] = mode_val
    _DEMO_STATE["message"] = data.get("message", "")
    _DEMO_STATE["theme"] = data.get("theme", "")
    if status_val != "idle" and not _DEMO_STATE["started"]:
        _DEMO_STATE["started"] = now
    if status_val == "idle":
        _DEMO_STATE["started"] = ""
    _DEMO_STATE["updated"] = now
    return jsonify(_DEMO_STATE), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))

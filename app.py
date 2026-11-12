import copy
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

APP_VERSION = os.environ.get("APP_VERSION", "dev")
DEMO_STATE_TOKEN = os.environ.get("DEMO_STATE_TOKEN", os.environ.get("WIP_TOKEN", "demo-wip-token"))
WIP_TOKEN = DEMO_STATE_TOKEN  # compatibilite avec l'ancien nom

VALID_STATUSES = ("idle", "in-progress", "deploying")
VALID_MODES = ("idle", "demo", "raz")
VALID_PIPELINE_STATES = ("pending", "running", "success", "failed")
PIPELINE_KEYS = ("code", "gitPush", "ci", "flux", "rollout", "health")

DEFAULT_PIPELINE = {key: "pending" for key in PIPELINE_KEYS}


def _default_demo_state():
    return {
        "status": "idle",
        "mode": "idle",
        "message": "",
        "theme": "",
        "started": "",
        "updated": "",
        "gitPushed": False,
        "pipeline": dict(DEFAULT_PIPELINE),
    }


# Stockage ephemere en memoire (suffisant pour une demo de quelques minutes).
_DEMO_STATE = _default_demo_state()


def _normalize_pipeline(pipeline):
    """Garantit un pipeline complet avec uniquement des etats valides."""
    result = dict(DEFAULT_PIPELINE)
    if isinstance(pipeline, dict):
        for key, value in pipeline.items():
            if key in PIPELINE_KEYS and value in VALID_PIPELINE_STATES:
                result[key] = value
    return result


def _normalize_demo_state(state):
    if not isinstance(state, dict):
        state = {}
    status = state.get("status", "idle")
    if status not in VALID_STATUSES:
        status = "idle"
    mode = state.get("mode", "idle")
    if mode not in VALID_MODES:
        mode = "idle"
    return {
        "status": status,
        "mode": mode,
        "message": "" if state.get("message") is None else (state.get("message", "") if isinstance(state.get("message", ""), str) else str(state.get("message", ""))),
        "theme": "" if state.get("theme") is None else (state.get("theme", "") if isinstance(state.get("theme", ""), str) else str(state.get("theme", ""))),
        "started": state.get("started", "") or "",
        "updated": state.get("updated", "") or "",
        "gitPushed": bool(state.get("gitPushed", False)),
        "pipeline": _normalize_pipeline(state.get("pipeline")),
    }


def _reset_demo_state():
    """Remet l'etat demo a sa valeur par defaut (idle)."""
    global _DEMO_STATE
    _DEMO_STATE = _default_demo_state()
    return _DEMO_STATE


def _init_demo_state_from_index(path=None):
    """Deduit l'etat initial de la demo depuis la page deployee (index.html).

    Cela rend l'etat persistant a travers les redemarrages de pod : la page
    'demo loading' embarque un marqueur demo-state=raz, une page de theme
    normale laisse l'etat a idle.
    """
    global _DEMO_STATE
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "index.html")
    try:
        with open(path, encoding="utf-8") as f:
            html = f.read()
    except OSError:
        return _DEMO_STATE
    if 'name="demo-state" content="raz"' in html or "name='demo-state' content='raz'" in html:
        now = datetime.now(timezone.utc).isoformat()
        _DEMO_STATE = _normalize_demo_state({
            "status": "idle",
            "mode": "raz",
            "message": "Démo en attente (page de chargement)",
            "theme": "demo-loading",
            "started": "",
            "updated": now,
            "gitPushed": False,
            "pipeline": dict(DEFAULT_PIPELINE),
        })
    else:
        _DEMO_STATE = _normalize_demo_state(_DEMO_STATE)
    return _DEMO_STATE


_init_demo_state_from_index()


def _demo_state_copy():
    return copy.deepcopy(_DEMO_STATE)


def _demo_state_response():
    return jsonify(_demo_state_copy())


@app.get("/")
def hello():
    return send_file(os.path.join(os.path.dirname(__file__), "index.html"))


@app.get("/healthz")
def healthz():
    return jsonify(status="ok", version=APP_VERSION, app="opencode")


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
    global _DEMO_STATE
    token = request.headers.get("X-Wip-Token", "") or request.headers.get("X-Demo-State-Token", "")
    if token != DEMO_STATE_TOKEN:
        return jsonify(error="unauthorized"), 401
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    now = datetime.now(timezone.utc).isoformat()

    # Mise a jour partielle : seuls les champs fournis sont modifies.
    status_val = data.get("status", _DEMO_STATE.get("status", "idle"))
    if status_val not in VALID_STATUSES:
        return jsonify(error="invalid status"), 400

    if "mode" in data:
        mode_val = data.get("mode")
        if mode_val not in VALID_MODES:
            return jsonify(error="invalid mode"), 400
    else:
        # Deduire le mode si un statut actif est envoye sans mode explicite.
        if status_val in ("in-progress", "deploying"):
            mode_val = "demo"
        elif "status" in data:
            mode_val = "idle" if status_val == "idle" else _DEMO_STATE.get("mode", "idle")
        else:
            mode_val = _DEMO_STATE.get("mode", "idle")

    current = _demo_state_copy()
    current["status"] = status_val
    current["mode"] = mode_val
    if "message" in data:
        current["message"] = data.get("message", "") if data.get("message") is not None else ""
    if "theme" in data:
        current["theme"] = data.get("theme", "") if data.get("theme") is not None else ""
    if "gitPushed" in data:
        current["gitPushed"] = bool(data.get("gitPushed"))
    if isinstance(data.get("pipeline"), dict):
        merged = dict(current["pipeline"])
        for key, value in data["pipeline"].items():
            if key in PIPELINE_KEYS and value in VALID_PIPELINE_STATES:
                merged[key] = value
        current["pipeline"] = _normalize_pipeline(merged)

    if status_val != "idle" and not current["started"]:
        current["started"] = now
    if status_val == "idle" and mode_val != "demo" and "status" in data:
        current["started"] = ""
        current["gitPushed"] = False
    current["updated"] = now

    _DEMO_STATE = _normalize_demo_state(current)
    return jsonify(_demo_state_copy()), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))

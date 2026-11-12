import os
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

APP_VERSION = os.environ.get("APP_VERSION", "dev")
WIP_TOKEN = os.environ.get("WIP_TOKEN", "demo-wip-token")

# Stockage éphémère en mémoire (suffisant pour une démo de quelques minutes).
_WIP = {"status": "idle", "message": "", "theme": "", "started": "", "updated": ""}


@app.get("/")
def hello():
    return send_file(os.path.join(os.path.dirname(__file__), "index.html"))


@app.get("/healthz")
def healthz():
    return jsonify(status="ok", version=APP_VERSION, app="natatio")


@app.get("/status")
def status():
    return send_file(os.path.join(os.path.dirname(__file__), "status.html"))


@app.get("/wip-status")
def wip_status_get():
    return jsonify(_WIP)


@app.post("/wip-status")
def wip_status_post():
    token = request.headers.get("X-Wip-Token", "")
    if token != WIP_TOKEN:
        return jsonify(error="unauthorized"), 401
    data = request.get_json(silent=True) or {}
    now = datetime.now(timezone.utc).isoformat()
    status_val = data.get("status", "idle")
    if status_val not in ("idle", "in-progress", "deploying"):
        return jsonify(error="invalid status"), 400
    _WIP["status"] = status_val
    _WIP["message"] = data.get("message", "")
    _WIP["theme"] = data.get("theme", "")
    if status_val != "idle" and not _WIP["started"]:
        _WIP["started"] = now
    if status_val == "idle":
        _WIP["started"] = ""
    _WIP["updated"] = now
    return jsonify(_WIP), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))

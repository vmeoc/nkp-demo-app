import os

from flask import Flask, jsonify, send_file

app = Flask(__name__)

APP_VERSION = os.environ.get("APP_VERSION", "dev")


@app.get("/")
def hello():
    return send_file(os.path.join(os.path.dirname(__file__), "index.html"))


@app.get("/healthz")
def healthz():
    return jsonify(status="ok", version=APP_VERSION, app="basket-jereme")


@app.get("/status")
def status():
    return send_file(os.path.join(os.path.dirname(__file__), "status.html"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))

import os

from flask import Flask, send_file

app = Flask(__name__)


@app.get("/")
def hello():
    return send_file(os.path.join(os.path.dirname(__file__), "index.html"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))

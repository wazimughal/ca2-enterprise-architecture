import os, json, time
from datetime import datetime, timezone
from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import requests as http

app = Flask(__name__)

SERVICE_KEY = os.getenv("SERVICE_KEY", "")
CHECKOUT_URL = os.getenv("CHECKOUT_URL", "http://localhost:5001/checkout")
SERVICE_NAME = "gateway"

REQUEST_COUNT = Counter("gateway_requests_total", "Total gateway requests", ["endpoint", "status"])
REQUEST_LATENCY = Histogram("gateway_request_duration_seconds", "Request duration", ["endpoint"])


def log_json(level, action, request_id="no-request-id", **extra):
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(),
             "service": SERVICE_NAME, "level": level,
             "request_id": request_id, "action": action}
    entry.update(extra)
    print(json.dumps(entry), flush=True)


@app.get("/")
def home():
    return jsonify({"service": "gateway", "message": "Gateway is running"})


@app.get("/api/ping")
def ping():
    return jsonify({"ok": True, "service": "gateway"})


@app.get("/api/arch")
def arch():
    return jsonify({"arch": "k3s-nanoservices-checkout",
                    "services": ["gateway", "checkout", "pricing", "inventory", "postgres"]})


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.post("/api/checkout")
def checkout():
    start = time.time()
    payload = request.get_json(silent=True) or {}
    request_id = request.headers.get("X-Request-Id", "no-request-id")
    log_json("INFO", "receive_checkout", request_id, payload=str(payload))

    headers = {"X-Request-Id": request_id, "X-Service-Key": SERVICE_KEY}

    try:
        log_json("INFO", "forward_checkout", request_id, url=CHECKOUT_URL)
        resp = http.post(CHECKOUT_URL, json=payload, headers=headers, timeout=3)
        log_json("INFO", "checkout_response", request_id, status=resp.status_code)
        REQUEST_COUNT.labels(endpoint="/api/checkout", status=str(resp.status_code)).inc()
        REQUEST_LATENCY.labels(endpoint="/api/checkout").observe(time.time() - start)
        return jsonify(resp.json()), resp.status_code
    except http.RequestException as e:
        log_json("ERROR", "checkout_failed", request_id, error=str(e))
        REQUEST_COUNT.labels(endpoint="/api/checkout", status="503").inc()
        REQUEST_LATENCY.labels(endpoint="/api/checkout").observe(time.time() - start)
        return jsonify({"ok": False, "request_id": request_id,
                        "error": f"Gateway could not reach checkout service: {str(e)}"}), 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

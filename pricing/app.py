import os
import json
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

SERVICE_KEY = os.getenv("SERVICE_KEY", "")
SERVICE_NAME = "pricing"

PRICE_LIST = {"SKU-001": 25, "SKU-002": 40, "SKU-003": 15}

REQUEST_COUNT = Counter("pricing_requests_total", "Total pricing requests", ["endpoint", "status"])
REQUEST_LATENCY = Histogram("pricing_request_duration_seconds", "Request duration", ["endpoint"])


def log_json(level, action, request_id="no-request-id", **extra):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": SERVICE_NAME, "level": level,
        "request_id": request_id, "action": action,
    }
    entry.update(extra)
    print(json.dumps(entry), flush=True)


def check_service_key():
    return SERVICE_KEY != "" and request.headers.get("X-Service-Key", "") == SERVICE_KEY


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "pricing"})


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.get("/price/<sku>")
def price(sku):
    start = time.time()
    request_id = request.headers.get("X-Request-Id", "no-request-id")

    if not check_service_key():
        log_json("WARNING", "auth_failed", request_id, result="unauthorized")
        REQUEST_COUNT.labels(endpoint="/price", status="401").inc()
        REQUEST_LATENCY.labels(endpoint="/price").observe(time.time() - start)
        return jsonify({"ok": False, "request_id": request_id,
                        "error": "Unauthorized: invalid or missing service key"}), 401

    log_json("INFO", "lookup_price", request_id, sku=sku)
    unit_price = PRICE_LIST.get(sku)

    if unit_price is None:
        log_json("WARNING", "price_lookup", request_id, sku=sku, result="not_found")
        REQUEST_COUNT.labels(endpoint="/price", status="404").inc()
        REQUEST_LATENCY.labels(endpoint="/price").observe(time.time() - start)
        return jsonify({"ok": False, "request_id": request_id, "error": "SKU not found"}), 404

    log_json("INFO", "price_lookup", request_id, sku=sku, unit_price=unit_price, result="success")
    REQUEST_COUNT.labels(endpoint="/price", status="200").inc()
    REQUEST_LATENCY.labels(endpoint="/price").observe(time.time() - start)
    return jsonify({"ok": True, "request_id": request_id, "sku": sku, "unit_price": unit_price})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)

import os
import json
import time
from datetime import datetime, timezone
from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

SERVICE_KEY = os.getenv("SERVICE_KEY", "")
SERVICE_NAME = "inventory"

STOCK = {"SKU-001": 10, "SKU-002": 0, "SKU-003": 5}

REQUEST_COUNT = Counter("inventory_requests_total", "Total inventory requests", ["endpoint", "status"])
REQUEST_LATENCY = Histogram("inventory_request_duration_seconds", "Request duration", ["endpoint"])


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
    return jsonify({"ok": True, "service": "inventory"})


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.get("/stock/<sku>")
def stock(sku):
    start = time.time()
    request_id = request.headers.get("X-Request-Id", "no-request-id")

    if not check_service_key():
        log_json("WARNING", "auth_failed", request_id, result="unauthorized")
        REQUEST_COUNT.labels(endpoint="/stock", status="401").inc()
        REQUEST_LATENCY.labels(endpoint="/stock").observe(time.time() - start)
        return jsonify({"ok": False, "request_id": request_id,
                        "error": "Unauthorized: invalid or missing service key"}), 401

    quantity = request.args.get("quantity", type=int)

    log_json("INFO", "check_stock", request_id, sku=sku, quantity=quantity)

    if quantity is None or quantity <= 0:
        log_json("WARNING", "check_stock", request_id, sku=sku, result="invalid_quantity")
        REQUEST_COUNT.labels(endpoint="/stock", status="400").inc()
        REQUEST_LATENCY.labels(endpoint="/stock").observe(time.time() - start)
        return jsonify({"ok": False, "request_id": request_id,
                        "error": "quantity must be a positive integer"}), 400

    available = STOCK.get(sku)

    if available is None:
        log_json("WARNING", "check_stock", request_id, sku=sku, result="not_found")
        REQUEST_COUNT.labels(endpoint="/stock", status="404").inc()
        REQUEST_LATENCY.labels(endpoint="/stock").observe(time.time() - start)
        return jsonify({"ok": False, "request_id": request_id, "error": "SKU not found"}), 404

    stock_available = available >= quantity
    log_json("INFO", "check_stock", request_id, sku=sku, available=available,
             stock_available=stock_available, result="success")
    REQUEST_COUNT.labels(endpoint="/stock", status="200").inc()
    REQUEST_LATENCY.labels(endpoint="/stock").observe(time.time() - start)
    return jsonify({
        "ok": True, "request_id": request_id, "sku": sku,
        "requested_quantity": quantity, "available_quantity": available,
        "stock_available": stock_available
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)

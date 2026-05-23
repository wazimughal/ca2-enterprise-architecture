import os, json, time
import psycopg2
from datetime import datetime, timezone
from flask import Flask, jsonify, request, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import requests as http

app = Flask(__name__)

SERVICE_KEY = os.getenv("SERVICE_KEY", "")
PRICING_URL = os.getenv("PRICING_URL", "http://localhost:5002")
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:5003")
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_NAME = os.getenv("DB_NAME", "checkoutdb")
DB_USER = os.getenv("DB_USER", "checkoutuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "checkoutpass")
DB_PORT = os.getenv("DB_PORT", "5432")
SERVICE_NAME = "checkout"

REQUEST_COUNT = Counter("checkout_requests_total", "Total checkout requests", ["endpoint", "status"])
REQUEST_LATENCY = Histogram("checkout_request_duration_seconds", "Request duration", ["endpoint"])


def log_json(level, action, request_id="no-request-id", **extra):
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(),
             "service": SERVICE_NAME, "level": level,
             "request_id": request_id, "action": action}
    entry.update(extra)
    print(json.dumps(entry), flush=True)


def check_service_key():
    return SERVICE_KEY != "" and request.headers.get("X-Service-Key", "") == SERVICE_KEY


def get_db():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER,
                            password=DB_PASSWORD, port=DB_PORT, connect_timeout=3)


def init_db():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS checkout_audit (
            id SERIAL PRIMARY KEY, request_id VARCHAR(100),
            sku VARCHAR(50), quantity INTEGER, unit_price INTEGER,
            total_price INTEGER, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        conn.commit(); cur.close(); conn.close()
        log_json("INFO", "init_db", result="success")
    except Exception as e:
        log_json("ERROR", "init_db", result="failed", error=str(e))


def save_audit(request_id, sku, quantity, unit_price, total_price):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO checkout_audit (request_id,sku,quantity,unit_price,total_price) VALUES (%s,%s,%s,%s,%s)",
                    (request_id, sku, quantity, unit_price, total_price))
        conn.commit(); cur.close(); conn.close()
        log_json("INFO", "audit_saved", request_id, sku=sku, total_price=total_price, result="success")
    except Exception as e:
        log_json("ERROR", "audit_saved", request_id, result="failed", error=str(e))


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "checkout"})


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.post("/checkout")
def checkout():
    start = time.time()
    data = request.get_json(silent=True) or {}
    sku = data.get("sku")
    quantity = data.get("quantity")
    request_id = request.headers.get("X-Request-Id", "no-request-id")

    log_json("INFO", "start_checkout", request_id, sku=sku, quantity=quantity)

    if not check_service_key():
        log_json("WARNING", "auth_failed", request_id, result="unauthorized")
        REQUEST_COUNT.labels(endpoint="/checkout", status="401").inc()
        REQUEST_LATENCY.labels(endpoint="/checkout").observe(time.time() - start)
        return jsonify({"ok": False, "request_id": request_id,
                        "error": "Unauthorized: invalid or missing service key"}), 401

    if not sku or not isinstance(quantity, int) or quantity <= 0:
        log_json("WARNING", "invalid_input", request_id)
        REQUEST_COUNT.labels(endpoint="/checkout", status="400").inc()
        REQUEST_LATENCY.labels(endpoint="/checkout").observe(time.time() - start)
        return jsonify({"ok": False, "request_id": request_id,
                        "error": "Invalid input. Provide sku and positive integer quantity."}), 400

    downstream = {"X-Request-Id": request_id, "X-Service-Key": SERVICE_KEY}

    try:
        log_json("INFO", "call_pricing", request_id, url=f"{PRICING_URL}/price/{sku}")
        pr = http.get(f"{PRICING_URL}/price/{sku}", headers=downstream, timeout=1.5)
        pr.raise_for_status()
        pricing_data = pr.json()
        log_json("INFO", "pricing_success", request_id, unit_price=pricing_data["unit_price"])
    except http.RequestException as e:
        log_json("ERROR", "pricing_failed", request_id, error=str(e))
        REQUEST_COUNT.labels(endpoint="/checkout", status="503").inc()
        REQUEST_LATENCY.labels(endpoint="/checkout").observe(time.time() - start)
        return jsonify({"ok": False, "request_id": request_id,
                        "error": "Pricing service unavailable"}), 503

    try:
        log_json("INFO", "call_inventory", request_id, url=f"{INVENTORY_URL}/stock/{sku}")
        ir = http.get(f"{INVENTORY_URL}/stock/{sku}", params={"quantity": quantity},
                      headers=downstream, timeout=1.5)
        ir.raise_for_status()
        inventory_data = ir.json()
        log_json("INFO", "inventory_success", request_id, stock_available=inventory_data["stock_available"])
    except http.RequestException as e:
        log_json("ERROR", "inventory_failed", request_id, error=str(e))
        REQUEST_COUNT.labels(endpoint="/checkout", status="503").inc()
        REQUEST_LATENCY.labels(endpoint="/checkout").observe(time.time() - start)
        return jsonify({"ok": False, "request_id": request_id,
                        "error": "Inventory service unavailable"}), 503

    unit_price = pricing_data["unit_price"]
    stock_available = inventory_data["stock_available"]
    total_price = unit_price * quantity

    if not stock_available:
        log_json("WARNING", "insufficient_stock", request_id, sku=sku)
        REQUEST_COUNT.labels(endpoint="/checkout", status="409").inc()
        REQUEST_LATENCY.labels(endpoint="/checkout").observe(time.time() - start)
        return jsonify({"ok": False, "request_id": request_id, "sku": sku,
                        "quantity": quantity, "error": "Insufficient stock"}), 409

    save_audit(request_id, sku, quantity, unit_price, total_price)
    log_json("INFO", "checkout_success", request_id, sku=sku, total_price=total_price)
    REQUEST_COUNT.labels(endpoint="/checkout", status="200").inc()
    REQUEST_LATENCY.labels(endpoint="/checkout").observe(time.time() - start)
    return jsonify({"ok": True, "request_id": request_id, "sku": sku, "quantity": quantity,
                    "unit_price": unit_price, "total_price": total_price,
                    "stock_available": stock_available, "message": "Checkout successful"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5001)

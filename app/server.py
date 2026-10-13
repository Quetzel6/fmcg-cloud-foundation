"""Operational API with optional bearer authentication for aggregate data."""
import hmac
import json
import logging
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .analytics import sales_summary

logger = logging.getLogger("cloud-foundation")

def database_ready():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        return False
    try:
        import psycopg
        with psycopg.connect(dsn, connect_timeout=3) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                return cursor.fetchone() == (1,)
    except Exception:
        # Never log connection strings or driver exceptions containing credentials.
        return False

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        start = time.monotonic()
        path = self.path.split("?", 1)[0]
        token = os.environ.get("API_AUTH_TOKEN", "")
        authorization = self.headers.get_all("Authorization", [])
        protected = path in ("/health/data", "/analytics/sales-summary")
        if protected and token and (len(authorization) != 1 or not hmac.compare_digest(authorization[0].encode(), ("Bearer " + token).encode())):
            code, payload = 401, {"error": "unauthorized"}
        elif path == "/health/live":
            code, payload = 200, {"status": "alive"}
        elif path == "/health/ready":
            ready = database_ready()
            code = 200 if ready else 503
            payload = {"status": "ready" if ready else "not_ready"}
        elif path in ("/health/data", "/analytics/sales-summary"):
            try:
                summary = sales_summary()
                code, payload = 200, (summary if path.startswith("/analytics/") else {"status": "data_ready", "as_of_date": summary["as_of_date"]})
            except Exception:
                code, payload = 503, {"status": "data_not_ready"}
        elif path == "/":
            code, payload = 200, {"service": "fmcg-cloud-foundation", "version": "0.2.0", "data": "synthetic aggregate endpoint"}
        else:
            code, payload = 404, {"error": "not_found"}
        body = json.dumps(payload).encode()
        self.send_response(code)
        if code == 401:
            self.send_header("WWW-Authenticate", "Bearer")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        logger.info(json.dumps({"event": "request", "status": code, "duration_ms": round((time.monotonic()-start)*1000, 2)}))
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Do not log user-controlled URLs or headers.

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ThreadingHTTPServer((os.environ.get("BIND_HOST", "127.0.0.1"), int(os.environ.get("PORT", "8080"))), Handler).serve_forever()

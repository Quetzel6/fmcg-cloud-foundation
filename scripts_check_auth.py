"""Check running local API authorization without printing the token."""
import json
from pathlib import Path
import urllib.request
import urllib.error

if __name__ == "__main__":
    tokens = [line.split("=", 1)[1] for line in Path(".env").read_text().splitlines() if line.startswith("API_AUTH_TOKEN=")]
    if len(tokens) != 1 or not tokens[0]:
        raise SystemExit("Run scripts_auth_setup.py first.")
    for path, token, expected in [("/health/live", None, 200), ("/health/ready", None, 200), ("/health/data", None, 401), ("/analytics/sales-summary", "invalid", 401), ("/health/data", tokens[0], 200), ("/analytics/sales-summary", tokens[0], 200)]:
        request = urllib.request.Request("http://127.0.0.1:8080" + path, headers={"Authorization": "Bearer " + token} if token else {})
        try:
            response = urllib.request.urlopen(request, timeout=15)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = json.load(response)
            if response.status != expected:
                raise SystemExit("Unexpected status for " + path + ": " + str(response.status))
            if path == "/analytics/sales-summary" and expected == 200:
                assert (body["row_count"], body["quantity"], body["amount_satang"]) == (150600, "1931506", "11929529809"), "Aggregate mismatch"
            print(json.dumps({"path": path, "status": response.status, "check": "passed"}))

import json
import urllib.error
import urllib.request

def check(path, expected):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080"+path, timeout=8) as response:
            code, body = response.status, json.load(response)
    except urllib.error.HTTPError as error:
        code, body = error.code, json.load(error)
    assert code == expected, (path, code, expected)
    print(json.dumps({"path": path, "status": code, "body": body}))

if __name__ == "__main__":
    import sys
    check("/health/live", 200)
    check("/health/ready", 503 if "--database-down" in sys.argv else 200)
    check("/missing", 404)

"""Create a local demo API token, preserving existing database credentials."""
import re
import secrets
from pathlib import Path

if __name__ == "__main__":
    path = Path(".env")
    if not path.is_file():
        raise SystemExit("Existing .env required.")
    text = path.read_text()
    tokens = re.findall(r"^API_AUTH_TOKEN=(.*)$", text, re.MULTILINE)
    if len(tokens) > 1 or (tokens and not re.fullmatch(r"[a-f0-9]{64}", tokens[0])):
        raise SystemExit("Invalid or duplicate API_AUTH_TOKEN; inspect .env privately.")
    if not tokens:
        path.write_text(text.rstrip("\n") + "\nAPI_AUTH_TOKEN=" + secrets.token_hex(32) + "\n")
    path.chmod(0o600)
    print("API token configured; existing credentials preserved.")

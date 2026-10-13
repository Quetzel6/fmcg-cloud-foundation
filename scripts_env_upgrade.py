"""Append the API password without changing the existing database password."""
import re
import secrets
from pathlib import Path
if __name__ == "__main__":
    path=Path(".env")
    if not path.is_file():
        raise SystemExit("Existing .env is required; do not reset the database password.")
    text=path.read_text()
    existing=re.findall(r"^API_DB_PASSWORD=(.*)$",text,re.MULTILINE)
    if len(existing)>1 or (existing and not re.fullmatch(r"[A-Za-z0-9]{32,128}",existing[0])):
        raise SystemExit("Invalid or duplicate API_DB_PASSWORD; inspect .env privately.")
    if not existing:
        path.write_text(text.rstrip("\n")+"\nAPI_DB_PASSWORD="+secrets.token_hex(24)+"\n")
    path.chmod(0o600)
    print("API password configured; existing POSTGRES_PASSWORD preserved.")

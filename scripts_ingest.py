"""Validated synthetic snapshot replacement in the dedicated cloud lab only."""
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent / "pipeline"
sys.path.insert(0, str(ROOT / "src"))
from fmcg.generate import generate
from fmcg.load import load
from app.access import grant_sales_read
if __name__ == "__main__":
    if os.environ.get("ALLOW_DEMO_REPLACE") != "yes":
        raise SystemExit("Set ALLOW_DEMO_REPLACE=yes only for the disposable cloud lab database.")
    data = Path("/tmp/fmcg-data")
    config = ROOT / "config/scenario.toml"
    try:
        generate(config, data)
        report = load(data, config, after_reconcile=grant_sales_read)
        print(json.dumps({"status":report["status"], "data_quality":report["data_quality"]["status"], "post_load":report["post_load"]}))
    except Exception as error:
        raise SystemExit("Synthetic ingest failed: " + type(error).__name__) from None

"""Export OpenAPI spec and Postman collection (Sprint 6, Day 40).

Run:
    venv\\Scripts\\python.exe scripts/export_openapi.py
"""

import json
from pathlib import Path

from src.api.main import app

ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "docs" / "openapi.json"
POSTMAN_PATH = ROOT / "docs" / "nifty100.postman_collection.json"


def build_postman_collection(openapi):
    """Translate the OpenAPI paths into one Postman request per GET route."""
    items = []
    v1_prefix = "/api/v1"
    for path, methods in sorted(openapi["paths"].items()):
        if not path.startswith(v1_prefix):
            continue
        for method, spec in methods.items():
            if method.lower() != "get":
                continue
            url_path = path[len(v1_prefix) :] or "/"
            query = []
            for param in spec.get("parameters", []):
                if param.get("in") == "query":
                    query.append(param["name"])
            url = {
                "raw": "{{baseUrl}}" + url_path,
                "host": ["{{baseUrl}}"],
                "path": url_path.strip("/").split("/") if url_path.strip("/") else [],
                "query": [{"key": q, "value": ""} for q in query],
            }
            items.append(
                {
                    "name": spec.get("summary", path),
                    "request": {
                        "method": "GET",
                        "header": [],
                        "url": url,
                        "description": spec.get("summary", ""),
                    },
                }
            )
    return {
        "info": {
            "name": "Nifty100 Data Foundation API",
            "version": openapi.get("info", {}).get("version", "0.6.0"),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": items,
        "variable": [{"key": "baseUrl", "value": "http://localhost:8000/api/v1"}],
    }


def main():
    openapi = app.openapi()

    OPENAPI_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_PATH.write_text(json.dumps(openapi, indent=2), encoding="utf-8")
    collection = build_postman_collection(openapi)
    POSTMAN_PATH.write_text(json.dumps(collection, indent=2), encoding="utf-8")
    print(f"OpenAPI spec     : {OPENAPI_PATH}")
    print(f"Postman collection: {POSTMAN_PATH}")


if __name__ == "__main__":
    main()

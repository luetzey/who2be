"""Exportiert die OpenAPI-Spec der FastAPI-App als versionierte Referenz.

Die Spec unter ``docs/reference/openapi.json`` ist die eingecheckte
API-Referenz (spec-first, Dokumentations-Standards); die Laufzeit-Doku
(``/docs``, ``/openapi.json``) wird aus derselben App generiert. Nach
API-Aenderungen neu ausfuehren und die Datei mitcommitten. Drift faengt
zusaetzlich der Contract-Test ``apps/api/tests/contract`` teilweise ab.

Aufruf aus dem Repo-Root: ``uv run python scripts/export_openapi.py``
"""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    from who2be_api.main import app

    spec = app.openapi()
    out = Path(__file__).resolve().parent.parent / "docs" / "reference" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"OpenAPI {spec['info']['version']}: {len(spec.get('paths', {}))} Pfade -> {out}")


if __name__ == "__main__":
    main()

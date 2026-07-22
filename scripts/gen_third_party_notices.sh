#!/usr/bin/env bash
# Generiert THIRD-PARTY-LICENSES.md (OSS-1, ADR-0033).
#
# Nutzt dieselben Tools wie die CI-License-Gates (ci.yml):
#   - Python: pip-licenses ueber den uv-Workspace (Superset: enthaelt auch
#     Dev-/Tooling-Pakete der synchronisierten Umgebung — bewusst inklusiv,
#     Ueber-Attribution ist unschaedlich)
#   - Web: license-checker-rseidelsohn --production (nur das ausgelieferte
#     Bundle, ohne devDependencies)
#
# Aufruf aus dem Repo-Root: bash scripts/gen_third_party_notices.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/THIRD-PARTY-LICENSES.md"

{
  echo "# Third-Party Licenses"
  echo
  echo "Who2Be selbst steht unter FSL-1.1-Apache-2.0 (siehe \`LICENSE\`)."
  echo "Dieses Dokument listet die Drittanbieter-Abhaengigkeiten der"
  echo "distribuierten Artefakte samt Lizenzen. Es wird generiert mit"
  echo "\`bash scripts/gen_third_party_notices.sh\` und nutzt dieselben Tools"
  echo "wie die CI-License-Gates (ADR-0033)."
  echo
  echo "Generiert am: $(date -u +%Y-%m-%d)"
  echo
  echo "## Python (uv-Workspace: who2be-api, who2be-mcp, who2be-models, who2be-billing)"
  echo
  (cd "$ROOT" && uv run --with pip-licenses python -m piplicenses \
    --format=markdown \
    --ignore-packages who2be-api who2be-mcp who2be-models who2be-billing pip-licenses)
  echo
  echo "## Web (apps/web, Production-Bundle ohne devDependencies)"
  echo
  (cd "$ROOT/apps/web" && npx license-checker-rseidelsohn \
    --production --excludePrivatePackages --markdown)
} > "$OUT"

echo "OK: $OUT geschrieben ($(wc -l < "$OUT") Zeilen)" >&2

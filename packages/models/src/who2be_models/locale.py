"""Content-Locale fuer mehrsprachige Versionen (ADR-0027, Stream D2).

Eine Persona/Playbook/Resource kann pro Sprache eine eigene Versionsreihe
fuehren (`*_version.locale`). Das Sprach-Set ist DB-seitig **offen** (kein
CHECK, User-Entscheidung 2026-06-04) — die Normalisierung/Validierung lebt
hier in der Anwendungs-Schicht. Heute bietet die UI `de`/`en` an; weitere
Sprachen brauchen keine Migration.

`DEFAULT_LOCALE` (`'de'`) deckt Bestandsdaten (implizit deutsch) und alle
Lese-Pfade ohne expliziten `locale`-Parameter (Backward-Compat).
"""

import re
from typing import Annotated

from pydantic import StringConstraints

# Default-Sprache: Bestand ist implizit deutsch (Migration 0042 setzt
# `DEFAULT 'de'`), und jeder Lese-Pfad ohne locale-Angabe liefert 'de'.
DEFAULT_LOCALE = "de"

# Normalisiertes, offenes Locale-Kuerzel. `to_lower` + `strip_whitespace`
# vereinheitlichen die Eingabe; die Laengen-Grenze schuetzt vor Wildwuchs.
# Die Form-Validierung (BCP-47-artig) laeuft im `normalize_locale`-Helper
# nach der Normalisierung — `StringConstraints.pattern` wuerde gegen den
# rohen, noch nicht ge-lower-ten Wert pruefen.
ContentLocale = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, min_length=2, max_length=12),
]

# BCP-47-artiges Kuerzel: `de`, `en`, `de-at`, `pt-br` — ohne das Set fest zu
# verdrahten (offenes Sprach-Set, ADR-0027).
_LOCALE_RE = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,8})?$")

# Sprachen, die die UI aktuell anbietet. Rein deskriptiv (kein DB-/Wire-Gate) —
# Quelle der Wahrheit fuer das Frontend-Sprach-Set und Tests.
SUPPORTED_LOCALES: tuple[str, ...] = ("de", "en")


def normalize_locale(value: str) -> str:
    """Trimmt + lowercased ein Locale-Kuerzel und prueft die Form.

    Wirft `ValueError` bei leerer oder formwidriger Eingabe. Zentral, damit
    Create-Validatoren und API-Query-Plumbing dieselbe Normalisierung teilen.
    """
    normalized = value.strip().lower()
    if not _LOCALE_RE.match(normalized):
        raise ValueError(f"Ungueltiges Locale-Kuerzel: {value!r}")
    return normalized

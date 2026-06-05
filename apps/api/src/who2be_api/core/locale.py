"""FastAPI-Dependency fuer den `?locale=`-Query-Parameter (Content-i18n).

Liest die Ziel-Sprache aus der Query, normalisiert sie (lowercase/trim) und
validiert die Form. Default `'de'` (ADR-0027) haelt alle Lese-/Schreib-Pfade
ohne explizite `locale`-Angabe backward-compatible. Ungueltige Kuerzel → 422.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status

from who2be_models import DEFAULT_LOCALE
from who2be_models.locale import normalize_locale


def locale_param(
    locale: Annotated[
        str,
        Query(
            max_length=12,
            description="Sprachvariante des Inhalts (z. B. 'de', 'en'). Default 'de'.",
        ),
    ] = DEFAULT_LOCALE,
) -> str:
    try:
        return normalize_locale(locale)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Ungueltiger locale-Parameter: {locale!r}.",
        ) from exc


# Wiederverwendbare Annotation fuer Router-Signaturen: `LocaleQuery` injiziert
# die normalisierte Ziel-Sprache aus `?locale=`.
LocaleQuery = Annotated[str, Depends(locale_param)]

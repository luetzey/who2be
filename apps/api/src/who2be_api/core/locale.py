"""FastAPI-Dependency fuer den `?locale=`-Query-Parameter (Sprachfilter).

„Ein Element, eine Sprache" (ADR-0045, Plan 2026-07-24): Sprache ist ein
Attribut der Identitaets-Zeile, nicht mehr eine Varianten-Achse pro Version.
`?locale=` existiert daher nur noch auf LISTEN-Endpoints — als optionaler
Filter auf `entity.locale`. Ohne Angabe wird NICHT gefiltert (alle Sprachen);
Detail-Routen kennen den Parameter nicht mehr. Ungueltige Kuerzel → 422.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Query, status

from who2be_models.locale import normalize_locale


def locale_filter_param(
    locale: Annotated[
        str | None,
        Query(
            max_length=12,
            description=(
                "Optionaler Sprachfilter auf die Element-Sprache (z. B. 'de', "
                "'en'). Ohne Angabe werden alle Sprachen geliefert."
            ),
        ),
    ] = None,
) -> str | None:
    if locale is None:
        return None
    try:
        return normalize_locale(locale)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Ungueltiger locale-Parameter: {locale!r}.",
        ) from exc


# Wiederverwendbare Annotation fuer Listen-Router-Signaturen: injiziert den
# normalisierten Sprachfilter aus `?locale=` (None = kein Filter).
LocaleFilterQuery = Annotated[str | None, Depends(locale_filter_param)]

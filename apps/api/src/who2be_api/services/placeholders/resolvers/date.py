"""Date-Resolver: aktuelles Datum gemaess Format-Slug (ISO-8601 / Deutsch)."""

from __future__ import annotations

import logging

import asyncpg

from who2be_api.services.placeholders._core import RenderContext, ResolveResult

logger = logging.getLogger(__name__)

# Deutsche Monatsnamen (kein babel im Repo — simple Map, einfach zu warten).
_DE_MONTHS = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]


class DateResolver:
    """Expandiert das aktuelle Datum gemaess `target_id`-Format-Slug.

    Unterstuetzte Slugs:
    - ``""`` (leer) -> ISO-8601: "2026-05-31"
    - ``"human"``   -> "31. Mai 2026" (Deutsch, via _DE_MONTHS-Map)

    Unbekannte Slugs werden wie ``""`` behandelt; ein Warning wird geloggt.
    Kein babel im Repo — einfache Map. Nie Miss.
    """

    async def resolve(
        self,
        target_id: str,
        ctx: RenderContext,
        db: asyncpg.Connection,  # noqa: ARG002  (nicht benoetigt, aber Teil des Protokolls)
    ) -> ResolveResult:
        now = ctx.now
        if target_id == "human":
            day = now.day
            month_name = _DE_MONTHS[now.month - 1]
            year = now.year
            return ResolveResult(text=f"{day}. {month_name} {year}")
        if target_id != "":
            logger.warning(
                "DateResolver: unbekannter Format-Slug '%s' — verwende ISO-8601",
                target_id,
            )
        return ResolveResult(text=now.strftime("%Y-%m-%d"))

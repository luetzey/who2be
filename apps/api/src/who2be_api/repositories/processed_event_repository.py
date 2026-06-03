"""Dedupe-Ledger fuer Provider-Webhooks (`processed_webhook_event`, Migration 0038).

Mollie (und andere Provider) liefern denselben Webhook-Ping bei Netz-/Timeout-
Retries mehrfach. Damit ein Replay keinen erneuten Effekt hat — insbesondere
keine bezahlte Erstzahlung zwei Subscriptions anlegt — beansprucht der
Webhook-Pfad jede `(provider, event_id)` **genau einmal**: der erste Claim
verarbeitet, jeder weitere ist No-Op.

Der Claim ist atomar (`INSERT … ON CONFLICT DO NOTHING RETURNING`), sodass auch
parallele Doppel-Pings nicht doppelt durchlaufen — der UNIQUE-Index entscheidet.
"""

from __future__ import annotations

from typing import Protocol

import asyncpg


class ProcessedEventRepository(Protocol):
    """Service-seitige Abstraktion fuer den Webhook-Dedupe-Ledger."""

    async def claim(self, provider: str, event_id: str) -> bool:
        """True, wenn dieser Aufruf das Event NEU beansprucht hat (verarbeiten).

        False ⇒ das Event wurde bereits verarbeitet (No-Op-Replay).
        """
        ...

    async def release(self, provider: str, event_id: str) -> None:
        """Gibt einen Claim wieder frei (nur bei fehlgeschlagener Verarbeitung).

        So bleibt ein Mollie-Retry wirksam, wenn der nicht-idempotente Schritt
        nach dem Claim (Subscription-Anlage/Upsert) scheitert — sonst waere das
        bezahlte Event dauerhaft No-Op.
        """
        ...


class PgProcessedEventRepository:
    """asyncpg-Implementierung von `ProcessedEventRepository`."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def claim(self, provider: str, event_id: str) -> bool:
        # Atomarer Claim: nur das erste INSERT liefert eine `id` zurueck; ein
        # konkurrierendes/wiederholtes Event trifft den UNIQUE-Index und bekommt
        # via DO NOTHING kein RETURNING ⇒ None ⇒ bereits verarbeitet.
        inserted = await self._pool.fetchval(
            "INSERT INTO processed_webhook_event (provider, event_id) "
            "VALUES ($1, $2) ON CONFLICT (provider, event_id) DO NOTHING "
            "RETURNING id",
            provider,
            event_id,
        )
        return inserted is not None

    async def release(self, provider: str, event_id: str) -> None:
        await self._pool.execute(
            "DELETE FROM processed_webhook_event WHERE provider = $1 AND event_id = $2",
            provider,
            event_id,
        )

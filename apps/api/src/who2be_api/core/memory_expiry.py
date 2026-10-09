"""Verfallsjob fuer unbestaetigtes Gedaechtnis (ADR-0053 3.1.3, Paket C2b).

Betroffen sind nur **unbestaetigte** Eintraege: `pending` und automatisch
aktivierte `active` ohne `confirmed_at`, deren `expires_at` erreicht ist. Den
Zeitpunkt setzt der Speicherpfad (`created_at + MEMORY_UNCONFIRMED_TTL_DAYS`,
gesetzte Annahme 30 Tage, ADR-0053 Anhang B); nur eine menschliche
Bestaetigung setzt ihn auf NULL. Abrufe verlaengern nichts — der Job schaut
weder auf `retrieval_count` noch auf `last_retrieved_at`.

Der Job setzt `status='expired'` und schreibt je Eintrag das Ereignis
`expired` (`actor_kind='system'`, Schnappschuss vorher/nachher). Er loescht
nicht: abgelaufene Eintraege bleiben Teil der Dublettenbasis, sonst reichte
der Agent denselben Fakt erneut ein (`find_similar` prueft alle Status).

Lernvorschlaege (`kind='lesson'`) sind ausgenommen: der DB-CHECK aus 0091
laesst fuer sie kein `expired` zu, und ihre Wiederholung ist Signal (3.1.6).

Laeuft als **Owner-Connection** (`DATABASE_URL`, RLS-Bypass) wie
`who2be-purge`, workspace-uebergreifend und nicht im Request-Pfad. Als Cron
einplanbar (`who2be-memory-expire`); idempotent — ein zweiter Lauf findet die
schon abgelaufenen Eintraege nicht mehr vor.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import asyncpg

# Schnappschuss wie `memory_repository._snapshot` (3.1.2): nie `context` oder
# `triage_note`.
_SNAPSHOT = (
    "jsonb_build_object('fact', {t}.fact, 'category', {t}.category, "
    "'importance', {t}.importance, 'status', {status}, 'kind', {t}.kind, "
    "'origin', {t}.origin)"
)

# Eine Anweisung, also atomar: Statuswechsel und Ereignis entstehen gemeinsam
# oder gar nicht. `FOR UPDATE SKIP LOCKED` laesst Zeilen aus, die gerade eine
# Triage haelt — der naechste Lauf nimmt sie, falls sie dann noch faellig sind.
# Die Bedingung `confirmed_at IS NULL` steht zusaetzlich zu `expires_at`: ein
# bestaetigter Eintrag verfaellt nie, auch wenn ein Altbestand oder ein
# kuenftiger Schreibpfad `expires_at` stehen liesse.
#
# `$1::timestamptz` gecastet — Muster `purge._EXPIRED_ARTIFACTS_SQL`.
_EXPIRE_SQL = f"""
WITH due AS (
    SELECT id, status AS old_status
    FROM agent_memory
    WHERE status IN ('pending', 'active')
      AND confirmed_at IS NULL
      AND kind <> 'lesson'
      AND expires_at IS NOT NULL
      AND expires_at <= $1::timestamptz
    FOR UPDATE SKIP LOCKED
),
expired AS (
    UPDATE agent_memory m
    SET status = 'expired', updated_at = now()
    FROM due
    WHERE m.id = due.id
    RETURNING m.id, m.workspace_id, m.created_by_agent_id,
              {_SNAPSHOT.format(t="m", status="due.old_status")} AS before,
              {_SNAPSHOT.format(t="m", status="'expired'")} AS after
)
INSERT INTO agent_memory_event
    (workspace_id, memory_id, event, actor_kind, agent_id, before, after)
SELECT workspace_id, id, 'expired', 'system', created_by_agent_id, before, after
FROM expired
RETURNING memory_id
"""


async def expire_unconfirmed_memories(
    conn: asyncpg.Connection,
    now: datetime | None = None,
) -> int:
    """Setzt faellige unbestaetigte Eintraege auf `expired`. Liefert die Anzahl."""
    reference = now or datetime.now(UTC)
    rows = await conn.fetch(_EXPIRE_SQL, reference)
    return len(rows)


def cli() -> None:
    """Console-Entrypoint fuer `who2be-memory-expire` (manueller Ausloeser, Notfallweg).

    Laeuft seit ADR-0057 §8 ueber den Worker-Store (`trigger='cli'`) und
    nimmt denselben Advisory-Lock wie die Worker-Routine `memory-expire`. Ist
    er belegt, endet der Aufruf mit Hinweis und Exit 0.
    """
    # Spaeter Import: `worker.routines` importiert dieses Modul.
    from who2be_api.worker.routines import MEMORY_EXPIRE, run_as_cli, skipped_message

    run = asyncio.run(run_as_cli(MEMORY_EXPIRE))
    if run.outcome.status == "skipped" or run.counters is None:
        print(skipped_message(MEMORY_EXPIRE))
        return
    count = run.counters["expired"]
    print(f"Gedaechtnis: {count} unbestaetigte(r) Eintrag/Eintraege abgelaufen.")


if __name__ == "__main__":
    cli()

"""Aufbewahrung der Nutzungs-Rohdaten und des Zugriffslogs (Owner E4b, E4c-b).

Zwei Fristen, eine Routine (`usage-retention`): `usage_event` (E4b, unten)
und seit E4c-b auch `agent_access_log`, ebenfalls 13 Kalendermonate, hier ab
`access_date` (`delete_expired_access_log`, Abschnitt am Ende). Der Worker
ruft beide in getrennten Transaktionen auf (`worker/routines.py`).

`usage_event` haelt jede Auslieferung an einen Agenten (`source='server'`,
Migration 0101) und jede Selbstauskunft (`agent_report`) als eigene Zeile.
E4b: „Jetzt 13 Monate festlegen und die Routine sofort bauen.“ Diese Funktion
loescht Rohzeilen, deren `created_at` aelter als 13 Kalendermonate ist.

Die Zaehler (Nutzung U1/U2: 7 und 30 Tage, Tagesreihe) und die Fallraten je
Version aus Phase E lesen weit innerhalb dieser Frist; sie aendern sich durch
den Lauf nicht. Was wegfaellt, ist nur die Historie jenseits von 13 Monaten
(„zuletzt genutzt“ und Gesamtsummen reichen hoechstens so weit zurueck,
ADR-0038-Nachtrag).

Die Frist rechnet Postgres in Kalendermonaten (`interval '13 months'`) ab dem
uebergebenen Zeitpunkt; der Worker uebergibt seinen Slot, nie `now()` der
Datenbank — mit fester Uhr testbar (Muster `core/audit_retention.py`).

Kein Index auf `created_at`: EXPLAIN auf 2 Mio. Zeilen ergab einen Seq Scan
um 0,5 s, bei einem Lauf am Tag. Ein Index muesste dagegen jeder INSERT auf
dem Auslieferungspfad mitpflegen (Plan
`.claude/plan/2026-10-10-1930_nutzung-u5-usage-retention.md`).

Laeuft als **Owner-Connection** (`DATABASE_URL`): `who2be_app` hat auf
`usage_event` und `agent_access_log` nur SELECT/INSERT (0053 bzw. 0079/0080,
append-only); keine Migration, keine SECURITY-DEFINER-Funktion. Auch fuer das
Zugriffslog kein Index auf `access_date`: es ist je Agent, Element, Operation
und Tag dedupliziert (Messung im PR zu E4c). Idempotent — ein zweiter
Lauf findet nichts mehr.
"""

from __future__ import annotations

from datetime import UTC, datetime

import asyncpg

#: Frist ab `created_at` (Owner E4b). Postgres-Intervall, Kalendermonate.
USAGE_EVENT_RETENTION = "13 months"

_DELETE_SQL = """
DELETE FROM usage_event
WHERE created_at < $1::timestamptz - $2::text::interval
"""
# `$2::text::interval`: asyncpg bindet `interval` nur als `timedelta`, und das
# kennt keine Kalendermonate.


async def delete_expired_usage_events(
    conn: asyncpg.Connection,
    now: datetime | None = None,
) -> int:
    """Loescht `usage_event`-Rohzeilen nach Fristablauf. Liefert die Anzahl."""
    reference = now or datetime.now(UTC)
    status: str = await conn.execute(_DELETE_SQL, reference, USAGE_EVENT_RETENTION)
    # asyncpg liefert den Command-Tag, z. B. "DELETE 3".
    return int(status.rsplit(" ", 1)[-1])


# --- agent_access_log (Owner E4c, Option b) ----------------------------------

#: Frist ab `access_date` (Owner E4c-b: „wie die Nutzungs-Rohdaten“).
ACCESS_LOG_RETENTION = "13 months"

_DELETE_ACCESS_LOG_SQL = """
DELETE FROM agent_access_log
WHERE access_date < (($1::timestamptz AT TIME ZONE 'UTC')::date - $2::text::interval)::date
"""
# `access_date` ist ein Kalendertag. Der Stichtag ist der UTC-Tag des Slots
# minus 13 Kalendermonate; eine Zeile genau von diesem Tag bleibt, erst der
# Tag davor faellt. Ein Monatsende rundet Postgres ab (31.03. → 28./29.02.).


async def delete_expired_access_log(
    conn: asyncpg.Connection,
    now: datetime | None = None,
) -> int:
    """Loescht `agent_access_log`-Zeilen nach Fristablauf. Liefert die Anzahl.

    Gleicher Weg wie `usage_event`: Owner-Connection, denn `who2be_app` hat
    auf dem Log nur SELECT/INSERT (0079/0080, append-only). Grants bleiben
    unveraendert; die App kann weiterhin nichts loeschen.
    """
    reference = now or datetime.now(UTC)
    status: str = await conn.execute(_DELETE_ACCESS_LOG_SQL, reference, ACCESS_LOG_RETENTION)
    return int(status.rsplit(" ", 1)[-1])

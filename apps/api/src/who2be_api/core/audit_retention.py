"""Endloeschung des anonymen Audit-Rests (Owner-Entscheidung E1a, Paket E1-2).

Faellt ein Workspace oder eine Organisation, anonymisiert der Trigger aus
Migration 0106 deren `audit_log`-Zeilen: Akteur → Sentinel, Ziel geleert,
`detail` auf die Allowlist gekuerzt, `anonymized_at` gesetzt. E1a: „Nach 12
Monaten loescht der Worker auch den anonymen Rest."

Anker ist `anonymized_at`, nicht `created_at` (Loeschkonzept §1, VVT): die Frist
laeuft ab der Loeschung des Scopes. Das Audit-Log lebender Workspaces
(`anonymized_at IS NULL`) beruehrt diese Routine nie, auch nicht seine alten
Zeilen. Zeilen, die nur der Konto-Purge anonymisiert hat, tragen kein
`anonymized_at` (der setzt nur `actor_id`) und bleiben ebenfalls.

Die Frist rechnet Postgres in Kalendermonaten (`interval '12 months'`) ab dem
uebergebenen Zeitpunkt; der Worker uebergibt seinen Slot, nie `now()` der
Datenbank — mit fester Uhr testbar (Muster `core/memory_expiry.py`).

Kein Index auf `anonymized_at`: ein Lauf am Tag ueber eine Tabelle mit
Admin-Ereignissen. Der Sequential Scan kostet dort weniger als ein Index, den
jeder INSERT mitpflegen muesste.

Laeuft als **Owner-Connection** (`DATABASE_URL`): `who2be_app` hat auf
`audit_log` nur SELECT/INSERT (0044, append-only). Idempotent — ein zweiter Lauf
findet nichts mehr.
"""

from __future__ import annotations

from datetime import UTC, datetime

import asyncpg

#: Frist ab `anonymized_at` (Owner E1a). Postgres-Intervall, Kalendermonate.
AUDIT_ANONYMIZED_RETENTION = "12 months"

_DELETE_SQL = """
DELETE FROM audit_log
WHERE anonymized_at IS NOT NULL
  AND anonymized_at < $1::timestamptz - $2::text::interval
"""
# `$2::text::interval`: asyncpg bindet `interval` nur als `timedelta`, und das
# kennt keine Kalendermonate.


async def delete_expired_anonymized_audit(
    conn: asyncpg.Connection,
    now: datetime | None = None,
) -> int:
    """Loescht anonymisierte `audit_log`-Zeilen nach Fristablauf. Liefert die Anzahl."""
    reference = now or datetime.now(UTC)
    status: str = await conn.execute(_DELETE_SQL, reference, AUDIT_ANONYMIZED_RETENTION)
    # asyncpg liefert den Command-Tag, z. B. "DELETE 3".
    return int(status.rsplit(" ", 1)[-1])

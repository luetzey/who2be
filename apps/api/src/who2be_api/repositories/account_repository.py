"""Persistenz fuer Account-/Org-Lifecycle (Track O, Plan §3.2).

Control-plane-Zugriffe (organization/org_member/workspace_member/api_token/
account_deletion tragen kein RLS): Soft-Delete einer Org, Vormerkung einer
Account-Loeschung sowie die Scan-/Purge-Queries fuer den Hard-Purge-Job.

Der Hard-Purge nutzt bewusst `DELETE FROM organization` — die bestehenden
ON-DELETE-CASCADE-FKs (workspace → persona/playbook/resource/agent/… →
*_version, plus org_entitlement/mcp_usage) raeumen die gesamte Tenant-Hierarchie
atomar ab.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

import asyncpg

from who2be_api.repositories.memory_repository import MEMORY_DELETED_AUDIT_ACTION

# Sentinel-UUID fuer anonymisierte Akteurs-/Subjekt-Verweise in Audit-Journalen
# (WP-D, ADR-0031). Nach DSGVO-Erasure wird `status_history.changed_by` und
# `audit_log.actor_id` des geloeschten Users hierauf gesetzt — Audit-Integritaet
# bleibt, PII-Bezug ist weg.
ANONYMIZED_USER_ID = UUID("00000000-0000-0000-0000-000000000000")

# Nutzergedaechtnis eines Menschen workspace-uebergreifend loeschen und je
# Zeile eine inhaltsfreie `audit_log`-Spur schreiben (ADR-0053 3.1.2, Weiche
# M5) — dieselbe Form wie `memory_repository._DELETE_WITH_AUDIT_SQL`, nur ohne
# Workspace-/Agent-Einschraenkung (Owner-Connection des Purge-Jobs) und mit
# Akteur NULL. Data-modifying CTE: Loeschen und Spur in einer Anweisung.
_PURGE_USER_MEMORY_SQL = (
    "WITH deleted AS ("
    "  DELETE FROM agent_memory WHERE scope = 'user' AND subject_user_id = $1 "
    "  RETURNING id, workspace_id"
    ") "
    "INSERT INTO audit_log (workspace_id, actor_id, action, target) "
    f"SELECT workspace_id, NULL::uuid, '{MEMORY_DELETED_AUDIT_ACTION}', id::text FROM deleted"
)

# jsonb-Listen eines Protokolls (`participants`, `dissent`, ADR-0053 3.5),
# deren Eintraege einen Menschen per `{<kind_key>: 'human', <id_key>: <uuid>}`
# nennen. Ersetzt nur die ID der passenden Eintraege durch den Sentinel ($2),
# Reihenfolge und uebrige Felder bleiben. Die IDs liegen als kanonischer
# UUID-Text vor (`SessionParticipant`/`SessionDissent`, mode="json"); der
# WHERE-Filter beruehrt nur Zeilen, die den User wirklich nennen.
_SESSION_LIST_COLUMNS: dict[str, tuple[str, str]] = {
    "participants": ("kind", "id"),
    "dissent": ("participant_kind", "participant_id"),
}


def _anonymize_session_list_sql(column: str, kind_key: str, id_key: str) -> str:
    """UPDATE fuer eine Personenliste in `feedback_session` (Whitelist-Guard)."""
    if _SESSION_LIST_COLUMNS.get(column) != (kind_key, id_key):
        raise ValueError(f"Unbekannte Protokoll-Liste: {column!r}")
    match = f"jsonb_build_object('{kind_key}', 'human', '{id_key}', $1::uuid::text)"
    return (
        f"UPDATE feedback_session SET {column} = ("  # noqa: S608 - Whitelist oben
        "  SELECT jsonb_agg(CASE WHEN item @> " + match + " "
        f"    THEN jsonb_set(item, '{{{id_key}}}', to_jsonb($2::uuid::text)) ELSE item END "
        "    ORDER BY ord) "
        f"  FROM jsonb_array_elements({column}) WITH ORDINALITY AS t(item, ord)"
        ") "
        f"WHERE {column} @> jsonb_build_array(" + match + ")"
    )


class AccountLifecycleRepository(Protocol):
    """Service-seitige Abstraktion fuer Lifecycle-Schreibzugriffe."""

    async def org_role(self, org_id: UUID, user_id: UUID) -> str | None: ...

    async def org_kind(self, org_id: UUID) -> str | None: ...

    async def soft_delete_organization(self, org_id: UUID, purge_after: datetime) -> datetime: ...

    async def sole_owner_company_orgs(self, user_id: UUID) -> list[str]: ...

    async def request_account_deletion(self, user_id: UUID, purge_after: datetime) -> None: ...


class PgAccountLifecycleRepository:
    """asyncpg-Implementierung (App-Pool, control-plane ohne RLS)."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def org_role(self, org_id: UUID, user_id: UUID) -> str | None:
        """Org-Rolle von `user_id` in `org_id`; `None`, wenn kein Mitglied."""
        role: str | None = await self._pool.fetchval(
            "SELECT role FROM org_member WHERE org_id = $1 AND user_id = $2",
            org_id,
            user_id,
        )
        return role

    async def org_kind(self, org_id: UUID) -> str | None:
        kind: str | None = await self._pool.fetchval(
            "SELECT kind FROM organization WHERE id = $1 AND deleted_at IS NULL",
            org_id,
        )
        return kind

    async def soft_delete_organization(self, org_id: UUID, purge_after: datetime) -> datetime:
        """Markiert die Org als zur Loeschung vorgemerkt; liefert den effektiven
        Purge-Termin. Idempotent: ist die Org bereits vorgemerkt, bleibt der
        urspruengliche `purge_after` bestehen und wird zurueckgegeben (kein
        verlaengertes Grace-Fenster bei erneutem Loeschen)."""
        stored: datetime | None = await self._pool.fetchval(
            "UPDATE organization SET deleted_at = now(), purge_after = $2 "
            "WHERE id = $1 AND deleted_at IS NULL RETURNING purge_after",
            org_id,
            purge_after,
        )
        if stored is not None:
            return stored
        existing: datetime | None = await self._pool.fetchval(
            "SELECT purge_after FROM organization WHERE id = $1",
            org_id,
        )
        return existing if existing is not None else purge_after

    async def sole_owner_company_orgs(self, user_id: UUID) -> list[str]:
        """Namen aktiver Company-Orgs, in denen `user_id` der EINZIGE Owner ist.

        Solche Orgs duerfen nicht ueber die Konto-Loeschung verwaist werden —
        der Service blockt die Account-Loeschung, bis sie uebertragen oder
        separat geloescht sind."""
        rows = await self._pool.fetch(
            "SELECT o.name FROM organization o "
            "JOIN org_member m ON m.org_id = o.id AND m.user_id = $1 AND m.role = 'owner' "
            "WHERE o.kind = 'company' AND o.deleted_at IS NULL "
            "  AND NOT EXISTS ("
            "    SELECT 1 FROM org_member m2 "
            "    WHERE m2.org_id = o.id AND m2.role = 'owner' AND m2.user_id <> $1"
            "  ) "
            "ORDER BY o.name ASC",
            user_id,
        )
        return [row["name"] for row in rows]

    async def request_account_deletion(self, user_id: UUID, purge_after: datetime) -> None:
        """Merkt den Account vor und mottet die Personal-Org des Users ein.

        Atomar; idempotent (mehrfaches Loeschen behaelt den fruehesten
        `purge_after`-Termin). Company-Orgs bleiben unangetastet — sie werden
        separat ueber `DELETE /v1/organizations/{id}` geloescht; der
        Account-Purge entfernt nur die Memberships des Users.
        """
        async with self._pool.acquire() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO account_deletion (user_id, purge_after) VALUES ($1, $2) "
                "ON CONFLICT (user_id) DO UPDATE SET "
                "  purge_after = LEAST(account_deletion.purge_after, EXCLUDED.purge_after), "
                "  purged_at = NULL",
                user_id,
                purge_after,
            )
            # Personal-Org des Users (slug == user_id, kind='personal') einmotten.
            await conn.execute(
                "UPDATE organization SET deleted_at = now(), purge_after = $2 "
                "WHERE kind = 'personal' AND slug = $1 AND deleted_at IS NULL",
                str(user_id),
                purge_after,
            )


class AccountPurgeRepository(Protocol):
    """Service-seitige Abstraktion fuer den Hard-Purge-Job (Owner-Connection)."""

    async def expired_organizations(self, now: datetime) -> list[UUID]: ...

    async def purge_organization(self, org_id: UUID) -> None: ...

    async def expired_accounts(self, now: datetime) -> list[UUID]: ...

    async def purge_account_data(self, user_id: UUID) -> int: ...

    async def cleanup_expired_invitations(self, now: datetime) -> int: ...

    async def cleanup_expired_oauth(self, now: datetime) -> int: ...

    async def mark_account_purged(self, user_id: UUID) -> None: ...


class PgAccountPurgeRepository:
    """asyncpg-Implementierung des Purge-Jobs auf einer Owner-Connection.

    Bewusst eine einzelne Connection (kein Pool): der Purge laeuft als
    Owner-Rolle (`DATABASE_URL`) ausserhalb von RLS, damit die CASCADE-Deletes
    workspace-uebergreifend durchgreifen.
    """

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def expired_organizations(self, now: datetime) -> list[UUID]:
        rows = await self._conn.fetch(
            "SELECT id FROM organization WHERE deleted_at IS NOT NULL AND purge_after <= $1",
            now,
        )
        return [row["id"] for row in rows]

    # Zugriffslog-Zeilen der Workspaces einer Org. Seit Migration 0080 haelt
    # der FK `agent_access_log.agent_id` den Agent-Delete auf (ON DELETE NO
    # ACTION statt CASCADE, Security-Review H5) — sonst raeumte ein normaler
    # API-Delete das Compliance-Protokoll mit ab. Der Purge ist der LEGITIME
    # Loeschpfad (Owner-Connection, DSGVO-Erasure) und muss die Zeilen daher
    # selbst entfernen, BEVOR die Organization-CASCADE die Agenten erreicht.
    _PURGE_ACCESS_LOG_SQL = (
        "DELETE FROM agent_access_log WHERE workspace_id IN "
        "(SELECT id FROM workspace WHERE org_id = $1)"
    )

    async def purge_organization(self, org_id: UUID) -> None:
        # CASCADE raeumt Workspaces, Entities, Versionen, Entitlement + Usage;
        # das Zugriffslog haengt bewusst NICHT am Cascade (s. o.).
        async with self._conn.transaction():
            await self._conn.execute(self._PURGE_ACCESS_LOG_SQL, org_id)
            await self._conn.execute("DELETE FROM organization WHERE id = $1", org_id)

    async def expired_accounts(self, now: datetime) -> list[UUID]:
        rows = await self._conn.fetch(
            "SELECT user_id FROM account_deletion WHERE purged_at IS NULL AND purge_after <= $1",
            now,
        )
        return [row["user_id"] for row in rows]

    async def purge_account_data(self, user_id: UUID) -> int:
        """Loescht die User-eigenen Daten und anonymisiert ueberlebende
        Audit-Referenzen. Liefert die Zahl der anonymisierten Audit-Zeilen.

        Atomar in einer Owner-Transaktion (RLS-Bypass + UPDATE-Recht trotz
        Append-only-REVOKE aus 0044 — WP-D):
          * Personal-Org loeschen (CASCADE der ganzen Hierarchie).
          * API-Tokens und Memberships loeschen. Der `api_token`-Delete raeumt
            per FK-CASCADE (0049) auch die `oauth_refresh_token`-Zeilen des
            Users ab — Refresh-Tokens haengen an `api_token_id`, nicht an einer
            eigenen `user_id`-Spalte.
          * `oauth_authorization_code`-Zeilen des Users loeschen (CMP-1): die
            Tabelle traegt `user_id` ohne CASCADE auf den User; nach der
            Konto-Loeschung sind die Codes wertlos.
          * `status_history.changed_by`, `audit_log.actor_id` sowie
            `usage_event.actor_id` und `agent_feedback.actor_id` (0053) des
            Users auf den Sentinel anonymisieren (Audit-/Telemetrie-Integritaet
            bleibt, PII weg).
          * `test_case.created_by` (nur `created_by_kind = 'human'`) und
            `test_run.reported_by_user_id` (0089) ebenso — Pruefaelle und
            -laeufe in fremden Workspaces bleiben als Nachweis stehen.
          * Nutzergedaechtnis (`agent_memory.scope = 'user'` mit
            `subject_user_id` = User, 0091) workspace-uebergreifend
            **loeschen**, je Zeile eine inhaltsfreie `audit_log`-Spur
            `memory.deleted`; die Historie faellt per Cascade.
            `agent_memory.confirmed_by` und `agent_memory_event.actor_id`
            (nur `actor_kind = 'human'`) auf den Sentinel, ebenso
            `agent_memory_proposal.decided_by` (0096).
          * Faelle (0100): `agent_case.reporter_user_id`,
            `agent_case_event.actor_id` (nur `actor_kind = 'human'`) und
            `agent_case_element.assigned_by` (nur `assigned_by_kind = 'human'`)
            auf den Sentinel — der Fall bleibt als Inhalt des Workspace stehen.
          * Gespraechsprotokolle und Massnahmen (0103, PM-6):
            `feedback_session.submitted_by` (nur `submitted_by_kind =
            'human'`), die IDs menschlicher Eintraege in `participants` und
            `dissent` sowie `measure_event.actor_id` (nur `actor_kind =
            'human'`) auf den Sentinel — Protokoll und Massnahme bleiben.
          * `entitlement_history` bleibt **bewusst unberuehrt** (gesetzliche
            Aufbewahrung §14b UStG / §147 AO, ADR-0031).
        """
        async with self._conn.transaction():
            personal_org = await self._conn.fetchval(
                "SELECT id FROM organization WHERE kind = 'personal' AND slug = $1",
                str(user_id),
            )
            if personal_org is not None:
                # Zugriffslog VOR der Org-CASCADE (s. `purge_organization`):
                # der FK auf `agent` blockiert seit 0080 sonst den Delete.
                await self._conn.execute(self._PURGE_ACCESS_LOG_SQL, personal_org)
            await self._conn.execute(
                "DELETE FROM organization WHERE kind = 'personal' AND slug = $1",
                str(user_id),
            )
            await self._conn.execute("DELETE FROM api_token WHERE owner_id = $1", user_id)
            await self._conn.execute(
                "DELETE FROM oauth_authorization_code WHERE user_id = $1", user_id
            )
            # Agent-Favoriten des Users (#427): `agent_favorite.user_id` traegt
            # wie `oauth_authorization_code` keinen FK auf den GoTrue-User
            # (kein Schema tut das), CASCADE greift hier also nicht. Ohne diese
            # Zeile ueberlebten die Sterne eines geloeschten Kontos in fremden
            # Workspaces, in denen der User Mitglied war.
            await self._conn.execute("DELETE FROM agent_favorite WHERE user_id = $1", user_id)
            await self._conn.execute("DELETE FROM org_member WHERE user_id = $1", user_id)
            await self._conn.execute("DELETE FROM workspace_member WHERE user_id = $1", user_id)
            sh_result = await self._conn.execute(
                "UPDATE status_history SET changed_by = $2 WHERE changed_by = $1",
                user_id,
                ANONYMIZED_USER_ID,
            )
            al_result = await self._conn.execute(
                "UPDATE audit_log SET actor_id = $2 WHERE actor_id = $1",
                user_id,
                ANONYMIZED_USER_ID,
            )
            ue_result = await self._conn.execute(
                "UPDATE usage_event SET actor_id = $2 WHERE actor_id = $1",
                user_id,
                ANONYMIZED_USER_ID,
            )
            fb_result = await self._conn.execute(
                "UPDATE agent_feedback SET actor_id = $2 WHERE actor_id = $1",
                user_id,
                ANONYMIZED_USER_ID,
            )
            # Pruefaelle + Prueflaeufe (ADR-0053 3.2, Migration 0089). Beide
            # haengen per CASCADE an `workspace`/`agent` und fallen mit der
            # Personal-Org oben; in FREMDEN Workspaces ueberleben sie den
            # Account und tragen die Person weiter. `test_run` ist fuer
            # `who2be_app` append-only, `test_case` nur in `status` aenderbar
            # — der Owner darf trotzdem (s. o.). `created_by` nur bei
            # `created_by_kind = 'human'`: bei 'agent' steht dort eine
            # Agent-ID, keine Person; der Filter haelt Agent-Zeilen auch bei
            # einer (theoretischen) UUID-Gleichheit heraus.
            tc_result = await self._conn.execute(
                "UPDATE test_case SET created_by = $2 "
                "WHERE created_by = $1 AND created_by_kind = 'human'",
                user_id,
                ANONYMIZED_USER_ID,
            )
            tr_result = await self._conn.execute(
                "UPDATE test_run SET reported_by_user_id = $2 WHERE reported_by_user_id = $1",
                user_id,
                ANONYMIZED_USER_ID,
            )
            # Nutzergedaechtnis (ADR-0053 3.1.1, Migration 0091): Fakten UEBER
            # diesen Menschen. Sie haengen an keinem Agenten (`agent_id IS
            # NULL` per CHECK) und fallen nur mit ihrem Workspace — in
            # FREMDEN Workspaces ueberlebten sie den Account. Geloescht, nicht
            # anonymisiert: ein Fakt ueber eine Person ohne die Person ist
            # wertlos, und anonymisiert bliebe der Inhalt stehen. Die Historie
            # (`agent_memory_event`) geht per FK-Cascade mit. Je Zeile bleibt
            # nur die inhaltsfreie Spur `memory.deleted` (Weiche M5; Akteur
            # NULL = System, wie in 0044 fuer Ereignisse ohne Akteur
            # vorgesehen). Laeuft NACH dem Personal-Org-Delete: was dort per
            # Cascade faellt, dokumentiert die Org-Loeschung (0091).
            await self._conn.execute(_PURGE_USER_MEMORY_SQL, user_id)
            # Personenverweise in ueberlebenden Gedaechtnis-Zeilen (Muster
            # `test_case.created_by` oben): wer einen Eintrag bestaetigt hat
            # und wer in der Historie als Mensch gehandelt hat. Bei
            # `actor_kind` 'agent'/'system' ist `actor_id` NULL (0091); der
            # Filter haelt die Zeilen trotzdem ausdruecklich heraus.
            mc_result = await self._conn.execute(
                "UPDATE agent_memory SET confirmed_by = $2 WHERE confirmed_by = $1",
                user_id,
                ANONYMIZED_USER_ID,
            )
            me_result = await self._conn.execute(
                "UPDATE agent_memory_event SET actor_id = $2 "
                "WHERE actor_id = $1 AND actor_kind = 'human'",
                user_id,
                ANONYMIZED_USER_ID,
            )
            # Wer einen Agenten-Vorschlag entschieden hat (0096) — der
            # Vorschlag bleibt als Nachweis am ueberlebenden Eintrag stehen.
            mp_result = await self._conn.execute(
                "UPDATE agent_memory_proposal SET decided_by = $2 WHERE decided_by = $1",
                user_id,
                ANONYMIZED_USER_ID,
            )
            # Faelle (ADR-0053 3.3, Migration 0100). Sie haengen per CASCADE an
            # `workspace`/`agent` und fallen mit der Personal-Org oben; in
            # FREMDEN Workspaces ueberleben sie den Account. Anonymisiert, nicht
            # geloescht: ein Fall handelt vom Verhalten eines Agenten, nicht
            # von der meldenden Person, und gehoert dem Workspace (Muster
            # `test_run.reported_by_user_id`). NULL ginge fuer
            # `reporter_user_id` nicht: der CHECK
            # `agent_case_human_reporter_check` (Weiche F2, kein anonymer
            # Kanal) verlangt bei `reporter_kind = 'human'` eine ID — der
            # Sentinel erfuellt ihn. Event-Akteur und Zuordnender nur bei
            # Menschen: bei Agenten steht dort eine Agent-ID, keine Person.
            cr_result = await self._conn.execute(
                "UPDATE agent_case SET reporter_user_id = $2 WHERE reporter_user_id = $1",
                user_id,
                ANONYMIZED_USER_ID,
            )
            ce_result = await self._conn.execute(
                "UPDATE agent_case_event SET actor_id = $2 "
                "WHERE actor_id = $1 AND actor_kind = 'human'",
                user_id,
                ANONYMIZED_USER_ID,
            )
            ca_result = await self._conn.execute(
                "UPDATE agent_case_element SET assigned_by = $2 "
                "WHERE assigned_by = $1 AND assigned_by_kind = 'human'",
                user_id,
                ANONYMIZED_USER_ID,
            )
            # Gespraechsprotokolle und Massnahmen (ADR-0053 3.5/3.6, Migration
            # 0103, PM-6): ohne Frist aufbewahrt wie Faelle, in FREMDEN
            # Workspaces ueberleben sie den Account. Anonymisiert, nicht
            # geloescht. Nur menschliche Verweise: bei `agent`/`builder`
            # steht dort eine Agent-ID. In `participants` und `dissent` wird
            # nur die ID des passenden Eintrags ersetzt; Rolle, Text und
            # Reihenfolge bleiben. `dissent` gehoert dazu, weil dort dieselbe
            # Person als `participant_id` steht — sonst liefe die
            # Anonymisierung der Teilnehmerliste ins Leere.
            ss_result = await self._conn.execute(
                "UPDATE feedback_session SET submitted_by = $2 "
                "WHERE submitted_by = $1 AND submitted_by_kind = 'human'",
                user_id,
                ANONYMIZED_USER_ID,
            )
            sp_result = await self._conn.execute(
                _anonymize_session_list_sql("participants", "kind", "id"),
                user_id,
                ANONYMIZED_USER_ID,
            )
            sd_result = await self._conn.execute(
                _anonymize_session_list_sql("dissent", "participant_kind", "participant_id"),
                user_id,
                ANONYMIZED_USER_ID,
            )
            mev_result = await self._conn.execute(
                "UPDATE measure_event SET actor_id = $2 "
                "WHERE actor_id = $1 AND actor_kind = 'human'",
                user_id,
                ANONYMIZED_USER_ID,
            )
        return (
            _count(sh_result)
            + _count(al_result)
            + _count(ue_result)
            + _count(fb_result)
            + _count(tc_result)
            + _count(tr_result)
            + _count(mc_result)
            + _count(me_result)
            + _count(mp_result)
            + _count(cr_result)
            + _count(ce_result)
            + _count(ca_result)
            + _count(ss_result)
            + _count(sp_result)
            + _count(sd_result)
            + _count(mev_result)
        )

    async def cleanup_expired_invitations(self, now: datetime) -> int:
        """Bereinigt die Klartext-`email` akzeptierter/abgelaufener Einladungen.

        Setzt `email` auf einen Marker, statt die Zeile zu loeschen — der
        Audit-Trail (`workspace_invitation`-Verlauf) bleibt formal erhalten,
        die PII (E-Mail) wird entfernt. Idempotent: schon bereinigte Zeilen
        traegt der WHERE-Filter beim naechsten Lauf nicht mehr.
        """
        result = await self._conn.execute(
            "UPDATE workspace_invitation SET email = '<redacted>' "
            "WHERE email <> '<redacted>' "
            "  AND (accepted_at IS NOT NULL OR expires_at < $1)",
            now,
        )
        return _count(result)

    async def cleanup_expired_oauth(self, now: datetime) -> int:
        """Raeumt wertlose OAuth-Zeilen ab (Datenminimierung, CMP-1) — analog
        `cleanup_expired_invitations` bei jedem Purge-Lauf.

        - `oauth_authorization_code`: abgelaufen ODER konsumiert. Codes sind
          single-use; `consume_code` filtert ohnehin auf `consumed_at IS NULL
          AND expires_at > now()` — ein Replay verhaelt sich nach dem Delete
          identisch (nicht gefunden).
        - `oauth_refresh_token`: nur ABGELAUFENE Zeilen. Konsumierte, noch
          nicht abgelaufene Glieder bleiben stehen: `consume_refresh_grace`
          (Grace-Retry kurz nach der Rotation) und die Ketten-Revocation
          (`revoke_refresh_chain`, `rotated_from`) brauchen sie; nach
          `expires_at` sind sie fuer beide Pfade wertlos.

        Idempotent: ein zweiter Lauf ohne neue faellige Zeilen ist ein No-op.
        Liefert die Zahl der geloeschten Zeilen (Codes + Refresh).
        """
        codes = await self._conn.execute(
            "DELETE FROM oauth_authorization_code WHERE expires_at < $1 OR consumed_at IS NOT NULL",
            now,
        )
        refresh = await self._conn.execute(
            "DELETE FROM oauth_refresh_token WHERE expires_at < $1",
            now,
        )
        return _count(codes) + _count(refresh)

    async def mark_account_purged(self, user_id: UUID) -> None:
        await self._conn.execute(
            "UPDATE account_deletion SET purged_at = now() WHERE user_id = $1",
            user_id,
        )


def _count(result: str) -> int:
    """Parst die Affected-Row-Zahl aus dem asyncpg-Statement-Result (z. B.
    'UPDATE 5'). Bei unerwartetem Format → 0."""
    parts = result.split()
    if len(parts) >= 2 and parts[-1].isdigit():
        return int(parts[-1])
    return 0

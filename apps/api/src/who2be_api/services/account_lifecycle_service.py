"""Geschaeftslogik fuer Account-/Org-Loeschung (Track O, Plan §3.2).

Beide Loeschungen sind **Soft-Deletes mit 30-Tage-Grace**: sie merken nur vor
(`deleted_at`/`purge_after` bzw. eine `account_deletion`-Zeile). Der eigentliche
Hard-Purge (inkl. GoTrue-User-Loeschung) laeuft spaeter im Job `core/purge.py`.

`GRACE_PERIOD` ist die Single-Source der Frist; der Purge-Job liest `purge_after`
und raeumt erst danach ab.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status

from who2be_api.repositories.account_repository import AccountLifecycleRepository
from who2be_models import AccountDeletionRead, OrganizationDeletionRead

GRACE_PERIOD = timedelta(days=30)


class AccountLifecycleService:
    """Vormerkung von Account- und Org-Loeschungen (kein Hard-Delete hier)."""

    def __init__(self, repo: AccountLifecycleRepository) -> None:
        self._repo = repo

    async def request_account_deletion(self, user_id: UUID) -> AccountDeletionRead:
        """Merkt den eigenen Account zur Loeschung vor (Personal-Org wird eingemottet)."""
        purge_after = datetime.now(UTC) + GRACE_PERIOD
        await self._repo.request_account_deletion(user_id, purge_after)
        return AccountDeletionRead(purge_after=purge_after)

    async def delete_organization(self, user_id: UUID, org_id: UUID) -> OrganizationDeletionRead:
        """Merkt eine Company-Org zur Loeschung vor — nur der Org-Owner darf das.

        404, wenn die Org nicht existiert (oder schon vorgemerkt ist); 400 fuer
        Personal-Orgs (die laufen ueber die Konto-Loeschung); 403, wenn der
        Aufrufer nicht Owner ist.
        """
        kind = await self._repo.org_kind(org_id)
        if kind is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organisation nicht gefunden.",
            )
        if kind == "personal":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Persoenliche Organisationen werden ueber die Konto-Loeschung entfernt.",
            )
        if not await self._repo.is_org_owner(org_id, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nur der Owner kann diese Organisation loeschen.",
            )
        purge_after = datetime.now(UTC) + GRACE_PERIOD
        await self._repo.soft_delete_organization(org_id, purge_after)
        return OrganizationDeletionRead(organization_id=str(org_id), purge_after=purge_after)

"""Konkrete `EntitlementPort`-Adapter (Cloud-Webhook-DB vs. On-Prem-Offline)."""

from who2be_api.licensing.adapters.cloud import CloudEntitlementAdapter
from who2be_api.licensing.adapters.onprem import OnPremEntitlementAdapter

__all__ = ["CloudEntitlementAdapter", "OnPremEntitlementAdapter"]

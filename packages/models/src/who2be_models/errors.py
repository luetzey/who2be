"""Strukturierte API-Fehler-Taxonomie (RFC 7807, WP-2 / #254).

`ApiProblem` ist der maschinenlesbare Fehler-Body, den die API bei den
zentralen Autorisierungs-/State-Machine-Gates als ``application/problem+json``
zurueckliefert. Ein Agent (oder das Web-Frontend) liest `reason` als stabilen
Enum-Schluessel und `actionable_by`, um zu entscheiden, ob er den Fehler selbst
beheben kann (`agent`), an einen Menschen eskalieren muss (`human`) oder die
Aktion endgueltig nicht erlaubt ist (`none`).

Felder folgen RFC 7807 (`type`, `title`, `status`, `detail`) und ergaenzen die
Who2Be-spezifischen, agenten-tauglichen Felder (`reason`, `actionable_by`,
`request_id`). `type`/`title`/`request_id` setzt der zentrale Exception-Handler
einmalig; die Call-Sites liefern nur `(status, reason, actionable_by, detail)`.

**ADR-0051 (#436, W0 von #402):** `ProblemReason` ist seit dieser Welle das
Fehler-Vokabular der ganzen API, nicht mehr nur das der Gates — es traegt
laengst WorkArea-, KB-, Ingest- und Blobstore-Gruende. Alle Fehlerantworten
ziehen ihren `reason` aus dieser einen Liste; zwei Serialisierungen teilen sie
sich: `ApiProblem` (RFC 7807, Gates) und `ApiErrorBody` (schlank, alles
uebrige). Ein zweiter Enum daneben waere eine Dublette.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

# Stabiler, maschinenlesbarer Grund eines Gate-Fehlers (D1). Bewusst ein
# geschlossenes Vokabular — ein Agent kann darauf deterministisch verzweigen,
# ohne den `detail`-Freitext zu parsen.
ProblemReason = Literal[
    "missing_capability",
    "approval_pending",
    "domain_disabled",
    "forbidden_transition",
    "insufficient_role",
    "workspace_mismatch",
    "mfa_required",
    "concurrent_conflict",
    "composite_child_inactive",
    "managed_aggregate",
    # WorkArea + Knowledge Base (ADR-0047/0048/0049, Plan 2026-08-13):
    "rev_conflict",  # 409 — Artifact-Patch mit veralteter expected_rev
    "evidence_missing",  # 422 — Kante ohne Evidence auf beiden Seiten
    "anchor_unresolvable",  # 422 — Anker/Beleg-Referenz nicht aufloesbar
    "tier_upgrade_forbidden",  # 422 — unzulaessige Tier-Hochstufung
    "correlation_underpowered",  # 422 — co_occurs_with mit n < 20 (detail: n)
    "area_forbidden",  # 403 — Write auf lesbare Area ohne Write-Grant
    "query_not_readonly",  # 403 — Tabellen-Query will schreiben (Authorizer)
    "convention_missing",  # 422 — Import ohne Quell-Konvention
    "rule_required",  # 422 — Kategorie ohne matchende aktive Regel
    "ingest_unsupported",  # 422 — Ingest-Format nicht unterstuetzt
    "ingest_too_large",  # 413 — Ingest ueber dem Byte-Limit
    "url_forbidden",  # 403 — URL vom SSRF-Guard geblockt
    "blobstore_unconfigured",  # 503 — Blob-Storage nicht konfiguriert
    "tablestore_unavailable",  # 503 — Tabellen-Store nicht beschreibbar
    # Allgemeine API-Fehlergruende (ADR-0051, #436 = W0 von #402). Ab hier ist
    # die Liste NICHT mehr nur "Gate-Gruende": sie ist das Fehler-Vokabular der
    # API. Die Werte darueber sind unveraendert; neue Gruende kommen hier dazu,
    # Welle fuer Welle, statt in einem zweiten Enum daneben.
    "agent_not_found",  # 404 — Agent existiert nicht (oder nicht sichtbar)
    "db_unavailable",  # 503 — Datenbank-Pool nicht initialisiert
    "last_workspace_undeletable",  # 409 — letzter Workspace einer Organization
]

# Wer den Fehler beheben kann: `agent` = der aufrufende Agent kann es selbst
# erneut/anders versuchen, `human` = es braucht einen Menschen (Rolle/MFA/
# Freischaltung), `none` = die Aktion ist hier endgueltig nicht erlaubt.
ActionableBy = Literal["agent", "human", "none"]


class ApiProblem(BaseModel):
    """RFC-7807-konformer Fehler-Body fuer die zentralen API-Gates (WP-2).

    Wird als ``application/problem+json`` serialisiert. `request_id` korreliert
    die Antwort mit den strukturierten Logs (gespiegelt aus dem
    `X-Request-ID`-Header); `None`, wenn keine Request-ID gebunden war.
    """

    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    detail: str
    actionable_by: ActionableBy
    reason: ProblemReason
    request_id: str | None = None


class ApiErrorBody(BaseModel):
    """Schlanker Fehler-Body fuer Nicht-Gate-Antworten (ADR-0051, #436).

    Zweite **Serialisierung** desselben Vokabulars — nicht ein zweites
    Vokabular: `reason` kommt aus derselben `ProblemReason`-Liste wie in
    `ApiProblem`. Unterschiedlich ist nur die Huelle. `ApiProblem` traegt
    RFC-7807-Ballast (`type`, `title`, `actionable_by`, `request_id`) und geht
    als ``application/problem+json`` raus; hier bleibt es bei ``application/
    json`` und dem `detail`, das die Clients heute schon lesen — deshalb ist
    die Ergaenzung an rund 79 Bestands-Stellen additiv und kein Breaking
    Change. Die Vereinheitlichung der beiden Huellen ist ein eigenes Vorhaben
    (#402, Weg C); der Client braucht sie nicht, weil er nur `reason` liest.

    `params` traegt die Werte, die in den uebersetzten Text interpoliert
    werden (i18next-Platzhalter). Fehlt es, wird das Feld weggelassen — eine
    Antwort ohne Platzhalter sieht aus wie vorher plus `reason`.
    """

    model_config = ConfigDict(extra="forbid")

    detail: str
    reason: ProblemReason
    params: dict[str, str | int] | None = None

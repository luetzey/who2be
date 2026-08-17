"""Geschaeftslogik der Knowledge Base (ADR-0047, WP7 — Spec D + E-Sichtbarkeit).

Schreibpfad-Gates (Plan-Stack, Muster `wa_artifacts`): Mensch →
`require_role(editor)`; Agent → `require_capability(kb_write|kb_edge_write)` +
`require_write_rate`. Reads filtern ueber `readable_area_ids` IN der Repo-SQL
(EINE wiederverwendete Sichtbarkeits-Bedingung, `kb_repository._visible_sql`)
— ein nicht sichtbarer Node ist von einem nicht existierenden nicht
unterscheidbar (Router → 404, kein Existenz-Leak).

Belegpflicht (Spec D): jeder Node traegt einen aufgeloesten `source_ref`
(Kind serverseitig abgeleitet); Kanten loesen from/to, saemtliche
Evidence-Anker und die `kb_node_source_area`-Pflege in EINER Transaktion —
ein unaufloesbarer Anker rollt alles zurueck (kein Teilzustand).

Tier-Regeln (Serverlogik O): Hochstufen auf `verified` per Update ist IMMER
422 `tier_upgrade_forbidden` (auch fuer Menschen — Heben auf verified ist
P2-UI-Thema); `hypothesis → derived` verlangt einen `additional_source_ref`
ANDERER Beleg-Art; Downgrades sind frei. `co_occurs_with` verlangt n >= 20 —
das sprechende 422 `correlation_underpowered` (tatsaechliches n im detail)
kommt von hier, VOR dem DB-CHECK.

Korrelations-Disziplin (Spec O §10.7 „Zeit ist eine Achse, Zusammenhang ist
eine Behauptung", WP18): (1) Inhaltliche Kanten (`supports`/`derived_from`/
`belongs_to`) duerfen je Seite nicht AUSSCHLIESSLICH mit Timeline-url:-Ankern
belegt sein (`_check_content_edge_evidence` — die harte Regel bleibt die
co_-Feld-Kopplung im Modell-Validator). (2) Haengt ein Node NUR an
`co_occurs_with`-Kanten, verlangt `hypothesis → derived` zusaetzlich einen
Inhalts-Beleg (artifact|blob) unter [source_ref, additional_source_ref] —
ein weiterer url:-Verweis hebt Ko-Okkurrenz nicht zur Ableitung. (3) Die
Fallzahl-Garantie (co_n) liegt bewusst NUR in `neighbors` — `get_node` und
`search` liefern Nodes ohne Kanten-Kontext (kein Modell-Aufbruch).

Zugriffslog (Spec F, WP14): erfolgreiche Agent-Zugriffe werden NACH der
Operation best-effort geloggt (`services/access_log.log_access`, No-op fuer
Menschen): Einzel-Read als ``(node, read)``, `create_node`/`update_node` als
``(node, write)``; `create_edge` loggt ``(node, write)`` auf BEIDE
Node-Seiten (sofern vorhanden) — eine Kante veraendert die Aussagekraft
beider Nodes. Sensitivity ist IMMER der Server-Stand des Nodes.
`neighbors`/`search` loggen NICHT (Titel/Snippet-artige Uebersichten, Muster
`wa_search`) — der Inhalt fliesst beim Einzel-Read, und DER loggt.

ARC-3: kein SQL, keine HTTPException — nur `ApiGateError`, das Repository und
der Anker-Resolver (`kb_anchors`). Not-Found-Faelle kommen als `None` zurueck;
der Router uebersetzt sie in 404.
"""

from __future__ import annotations

import logging
from uuid import UUID

import asyncpg
from fastapi import status

from who2be_api.core.errors import ApiGateError
from who2be_api.core.security import (
    WorkspaceContext,
    require_capability,
    require_role,
    require_write_rate,
)
from who2be_api.core.workarea_scope import is_agent_bound, readable_area_ids
from who2be_api.repositories.agent_access_log_repository import AccessOperation
from who2be_api.repositories.kb_repository import KbRepository
from who2be_api.repositories.work_area_repository import WorkAreaRepository
from who2be_api.repositories.workspace_repository import WorkspaceRepository
from who2be_api.services.access_log import log_access
from who2be_api.services.content_locale import resolve_content_locale
from who2be_api.services.kb_anchors import (
    ResolvedAnchor,
    resolve_anchor,
    resolve_edge_end,
    resolve_source_ref,
)
from who2be_models import (
    AgentCapability,
    EdgeType,
    KbEdgeCreate,
    KbEdgeRead,
    KbNeighbor,
    KbNodeCreate,
    KbNodeRead,
    KbNodeUpdate,
    KbSearchHit,
    NodeTier,
    Sensitivity,
    SourceRefKind,
    WorkspaceRole,
)

logger = logging.getLogger(__name__)

# Mindest-Fallzahl einer co_occurs_with-Korrelation (Spec O; DB-Backstop:
# CHECK co_n >= 20 in 0077 — das sprechende 422 liefert dieser Service).
_CO_OCCURS_MIN_N = 20

# Tier-Leiter fuer Upgrade-Erkennung (hypothesis < derived < verified).
_TIER_ORDER: dict[NodeTier, int] = {
    NodeTier.hypothesis: 0,
    NodeTier.derived: 1,
    NodeTier.verified: 2,
}

# Kantentypen mit INHALTLICHER Behauptung (Spec O §10.7, WP18): ihre
# Belegkraft darf nicht allein aus zeitlicher Naehe stammen — dafuer gibt es
# ausschliesslich `co_occurs_with`. (`contradicts`/`supersedes` bleiben
# draussen: der Spec-Schnitt nennt genau diese drei.)
_CONTENT_EDGE_TYPES = frozenset({EdgeType.supports, EdgeType.derived_from, EdgeType.belongs_to})

# Substring, an dem ein url:-Evidence-Anker als Verweis auf den EIGENEN
# Timeline-Endpunkt erkennbar ist (`GET .../timeline`, WP15).
_TIMELINE_URL_MARKER = "/timeline"

# Inhalts-Belege im Sinne der O-Regeln: im Workspace aufloesbares Material
# (Artifact/Block oder Blob). `url:` ist ein EXTERNER Verweis ohne
# serverseitig pruefbaren Inhalt und zaehlt nicht als Inhalts-Beleg.
_CONTENT_EVIDENCE_KINDS = frozenset({SourceRefKind.artifact, SourceRefKind.blob})


def _is_timeline_url_anchor(anchor: str) -> bool:
    """True fuer url:-Anker, deren URL auf den Timeline-Endpunkt zeigt."""
    text = anchor.strip()
    return text.startswith("url:") and _TIMELINE_URL_MARKER in text


def _check_content_edge_evidence(data: KbEdgeCreate) -> None:
    """Spec O §10.7 (WP18): aus Gleichzeitigkeits-Evidence nur `co_occurs_with`.

    Inhaltliche Kanten (`supports`/`derived_from`/`belongs_to`) brauchen je
    Seite mindestens einen Beleg JENSEITS der Zeitachse. Pragmatischer
    Schnitt: verboten ist der eindeutig erkennbare Fall, dass ALLE
    Evidence-Anker einer Seite `url:`-Anker auf den eigenen
    Timeline-Endpunkt sind (`/timeline`-Substring) → 422 `evidence_missing`.

    Dokumentierte Grenze: der Server kann Belege nicht semantisch bewerten —
    ob ein Artifact-Anker inhaltlich traegt, bleibt beim Kurator. Die HARTE
    Regel ist die co_-Feld-Kopplung im Modell-Validator (`KbEdgeCreate`: nur
    `co_occurs_with` traegt co_query/co_n/co_from/co_to, andere Typen duerfen
    KEINE co_-Felder tragen); diese Zusatzpruefung faengt nur den
    offensichtlichen Missbrauch ab und bleibt bewusst klein.
    """
    if data.type not in _CONTENT_EDGE_TYPES:
        return
    for side, anchors in (("from", data.evidence_from), ("to", data.evidence_to)):
        if all(_is_timeline_url_anchor(anchor) for anchor in anchors):
            raise ApiGateError(
                status=status.HTTP_422_UNPROCESSABLE_CONTENT,
                reason="evidence_missing",
                actionable_by="agent",
                detail=(
                    f"'{data.type.value}' behauptet einen inhaltlichen Zusammenhang, "
                    f"aber alle Evidence-Anker der Seite '{side}' sind url:-Anker auf "
                    "den Timeline-Endpunkt (/timeline). Zeitliche Naehe belegt nur "
                    "co_occurs_with — mindestens einen Beleg jenseits der Zeitachse "
                    "ergaenzen (Artifact/Block, sha256 oder externe Quelle)."
                ),
            )


def _tier_upgrade_forbidden(detail: str) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        reason="tier_upgrade_forbidden",
        actionable_by="human",
        detail=detail,
    )


def _correlation_underpowered(co_n: int) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        reason="correlation_underpowered",
        actionable_by="agent",
        detail=(
            f"co_occurs_with verlangt mindestens n={_CO_OCCURS_MIN_N} Faelle — "
            f"tatsaechliches n={co_n}. Korrelation mit breiterem Zeitfenster "
            "oder mehr Daten erneut belegen."
        ),
    )


def _no_node_side(from_anchor: str, to_anchor: str) -> ApiGateError:
    return ApiGateError(
        status=status.HTTP_422_UNPROCESSABLE_CONTENT,
        reason="anchor_unresolvable",
        actionable_by="agent",
        detail=(
            f"Mindestens eine Kanten-Seite muss ein bestehender KB-Node sein "
            f"(node:<uuid>) — '{from_anchor}' und '{to_anchor}' sind beide "
            "keine KB-Nodes."
        ),
    )


class KbService:
    """KB-Nodes, -Kanten, Nachbarschaft und Suche ueber dem `KbRepository`."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        repo: KbRepository,
        work_areas: WorkAreaRepository,
        *,
        workspace_repo: WorkspaceRepository,
    ) -> None:
        self._pool = pool
        self._repo = repo
        self._work_areas = work_areas
        # Nur fuer die Content-Sprache (0082): sie steuert die FTS-Config der
        # generierten `search`-Spalte. Muster `WaArtifactService`.
        self._workspaces = workspace_repo

    # ------------------------------------------------------------------ Gates

    def _require_write(self, ctx: WorkspaceContext, capability: AgentCapability) -> None:
        """Schreib-Gate (H1, Muster `resource_service.create`): IMMER zuerst
        `require_role(editor)` — die Rolle ist auch bei agent-gebundenen
        Tokens am Token gepinnt (ein viewer-Token schreibt nie) —, danach
        Capability + Rate (fuer Menschen/JWT No-Ops)."""
        require_role(ctx, WorkspaceRole.editor)
        require_capability(ctx, capability)
        require_write_rate(ctx)

    def _actor(self, ctx: WorkspaceContext) -> UUID:
        """Akteur-UUID fuer `created_by`: der gebundene Agent, sonst der Mensch."""
        return ctx.agent_id if ctx.agent_id is not None else ctx.user_id

    # ------------------------------------------------------------------ Writes

    async def create_node(self, ctx: WorkspaceContext, data: KbNodeCreate) -> KbNodeRead:
        """Legt einen belegten Node an (Spec D).

        `source_ref` wird scope-bewusst aufgeloest (422 `anchor_unresolvable`)
        und liefert den `source_ref_kind`; in DERSELBEN Transaktion entstehen
        die `kb_node_source_area`-Rows aus den Areas der referenzierten
        Artifacts (`source_ref` + optionaler `content_ref`).
        """
        self._require_write(ctx, AgentCapability.kb_write)
        restrict = await readable_area_ids(self._pool, ctx)
        async with self._pool.acquire() as conn, conn.transaction():
            source = await resolve_source_ref(
                self._repo, conn, ctx.workspace_id, data.source_ref, restrict_area_ids=restrict
            )
            areas: set[UUID] = set()
            if source.area_id is not None:
                areas.add(source.area_id)
            if data.content_ref is not None:
                content_res = await resolve_anchor(
                    self._repo,
                    conn,
                    ctx.workspace_id,
                    data.content_ref,
                    restrict_area_ids=restrict,
                )
                if content_res.area_id is not None:
                    areas.add(content_res.area_id)
            if not areas and restrict is not None and ctx.agent_id is not None:
                # H2 (Security-Review 2026-08-13): Nodes area-beschraenkter
                # Aufrufer mit rein externem Beleg (url:/sha256: ohne lesbares
                # Artifact) duerfen NICHT sourcelos — und damit workspace-weit
                # sichtbar — entstehen. Sie erben die private Area des
                # Agenten; wer breiter teilen will, zitiert Artifact-Belege
                # aus shared Areas. Menschen (editor+, unrestricted) legen
                # weiterhin workspace-sichtbare kuratierte Aussagen an.
                private = await self._work_areas.get_or_create_private_area(
                    ctx.workspace_id, ctx.agent_id
                )
                if private is not None:
                    areas.add(private.id)
            node = await self._repo.insert_node(
                conn,
                ctx.workspace_id,
                tier=data.tier.value,
                content=data.content,
                content_ref=data.content_ref,
                source_ref=data.source_ref,
                source_ref_kind=source.source_kind.value,
                sensitivity=data.sensitivity.value,
                occurred_at=data.occurred_at,
                occurred_precision=data.occurred_precision.value,
                created_by=self._actor(ctx),
                # Sprache aus dem Workspace, nicht vom Client: sie steuert die
                # FTS-Config des Index (0082), und `KbNodeCreate` traegt
                # bewusst kein `locale` — ein Agent soll die Sprache nicht
                # waehlen muessen, sie steht schon am Workspace (Muster
                # `WaArtifactService._locale`).
                locale=await resolve_content_locale(self._workspaces, ctx.workspace_id, None),
            )
            await self._repo.add_source_areas(conn, ctx.workspace_id, node.id, sorted(areas))
        await self._log_node(ctx, node.id, "write", node.sensitivity)
        return node

    async def update_node(
        self, ctx: WorkspaceContext, node_id: UUID, data: KbNodeUpdate
    ) -> KbNodeRead | None:
        """Teilupdate mit Tier-Regeln (Serverlogik O); `None` = nicht sichtbar.

        - Hochstufen auf `verified` per Update: IMMER 422
          `tier_upgrade_forbidden` (auch fuer Menschen).
        - `hypothesis → derived`: NUR mit `additional_source_ref`, dessen
          aufgeloester Kind sich vom bestehenden `source_ref_kind`
          unterscheidet; dessen Artifact-Areas fliessen ZUSAETZLICH in
          `kb_node_source_area`. Der Primaer-`source_ref` bleibt in v1
          unveraendert — der Zweitbeleg wird (noch) nicht als eigene Spalte
          gefuehrt, nur seine Areas und die Tier-Entscheidung wirken.
        - Korrelations-Disziplin (Spec O §10.7, WP18): haengt der Node NUR
          an `co_occurs_with`-Kanten, braucht `hypothesis → derived`
          zusaetzlich einen Inhalts-Beleg (artifact|blob) unter
          [source_ref, additional_source_ref] — s. `_check_tier_transition`.
        - Downgrades (z. B. `derived → hypothesis`) sind frei.
        """
        restrict = await readable_area_ids(self._pool, ctx)
        async with self._pool.acquire() as conn, conn.transaction():
            current = await self._repo.get_node(
                conn, ctx.workspace_id, node_id, restrict_area_ids=restrict
            )
            if current is None:
                return None
            self._require_write(ctx, AgentCapability.kb_write)
            if is_agent_bound(ctx):
                # M5 (Security-Review 2026-08-13): Sichtbarkeit ist keine
                # Schreib-Erlaubnis. Agenten aendern nur eigene Nodes, und
                # `verified` (menschlich kuratiert) bleibt fuer Agenten
                # unantastbar — sonst liesse sich kuratiertes Wissen leise
                # verfaelschen. `area_forbidden` ist der bestehende
                # 403-Reason fuer fehlende Schreibrechte an WorkArea-/KB-
                # Objekten (keine neue Taxonomie fuer denselben Sachverhalt).
                # `created_by` kommt als String aus dem Read-Modell (die DB
                # speichert die nackte Akteur-UUID) — fuer den Vergleich
                # normalisieren.
                if current.created_by != str(ctx.agent_id):
                    raise ApiGateError(
                        status=status.HTTP_403_FORBIDDEN,
                        reason="area_forbidden",
                        actionable_by="human",
                        detail=(
                            "Nur der erstellende Agent (oder ein Mensch ab "
                            "editor) darf diesen Node aendern."
                        ),
                    )
                if current.tier == NodeTier.verified:
                    raise ApiGateError(
                        status=status.HTTP_403_FORBIDDEN,
                        reason="area_forbidden",
                        actionable_by="human",
                        detail=(
                            "Nodes der Stufe 'verified' aendern nur Menschen "
                            "(editor+) — Agenten koennen kuratierte Aussagen "
                            "nicht umschreiben."
                        ),
                    )
            additional: ResolvedAnchor | None = None
            if data.additional_source_ref is not None:
                additional = await resolve_source_ref(
                    self._repo,
                    conn,
                    ctx.workspace_id,
                    data.additional_source_ref,
                    restrict_area_ids=restrict,
                )
            if data.tier is not None:
                await self._check_tier_transition(
                    conn, ctx.workspace_id, current, data.tier, additional
                )
            updated = await self._repo.update_node(
                conn,
                ctx.workspace_id,
                node_id,
                content=data.content,
                tier=data.tier.value if data.tier is not None else None,
            )
            if updated is not None and additional is not None and additional.area_id is not None:
                await self._repo.add_source_areas(
                    conn, ctx.workspace_id, node_id, [additional.area_id]
                )
        if updated is not None:
            await self._log_node(ctx, node_id, "write", updated.sensitivity)
        return updated

    async def _check_tier_transition(
        self,
        conn: asyncpg.Connection,
        workspace_id: UUID,
        current: KbNodeRead,
        target: NodeTier,
        additional: ResolvedAnchor | None,
    ) -> None:
        """Erzwingt die Tier-Leiter (s. `update_node`-Docstring) — oder wirft.

        Korrelations-Disziplin (Spec O §10.7, WP18): haengt der Node
        AUSSCHLIESSLICH an `co_occurs_with`-Kanten, verlangt
        `hypothesis → derived` zusaetzlich mindestens einen Inhalts-Beleg
        (artifact|blob) unter [source_ref, additional_source_ref] — ein
        weiterer url:-Verweis macht aus Ko-Okkurrenz keine Ableitung. Die
        Pruefung laeuft VOR der Kind-Verschiedenheit, damit das 422 den
        eigentlichen Mangel benennt („nur Ko-Okkurrenz-Belege"); ohne Kanten
        oder mit mindestens einer inhaltlichen Kante greift sie nicht. Der
        Kanten-Lookup laeuft nur, wenn kein Inhalts-Beleg vorliegt.
        """
        if _TIER_ORDER[target] <= _TIER_ORDER[current.tier]:
            return  # Downgrade oder gleichbleibend: frei.
        if target == NodeTier.verified:
            raise _tier_upgrade_forbidden(
                f"Hochstufen von '{current.tier.value}' auf 'verified' per Update "
                "ist nicht erlaubt — verified vergibt nur die P2-Review-UI."
            )
        # Verbleibt: hypothesis → derived.
        if additional is None:
            raise _tier_upgrade_forbidden(
                "hypothesis → derived verlangt einen `additional_source_ref` "
                "(zusaetzlicher Beleg anderer Art)."
            )
        if not ({current.source_ref_kind, additional.source_kind} & _CONTENT_EVIDENCE_KINDS):
            edge_types = await self._repo.edge_types_for_node(conn, workspace_id, current.id)
            if edge_types == {EdgeType.co_occurs_with.value}:
                raise _tier_upgrade_forbidden(
                    "hypothesis → derived scheitert: dieser Node hat nur "
                    "Ko-Okkurrenz-Belege (alle Kanten sind co_occurs_with) und "
                    "weder source_ref noch additional_source_ref ist ein "
                    "Inhalts-Beleg (artifact|blob). Zeitliche Naehe wird durch "
                    "einen weiteren url:-Verweis nicht zur Ableitung — einen "
                    "inhaltlichen Beleg ergaenzen."
                )
        if additional.source_kind.value == current.source_ref_kind.value:
            raise _tier_upgrade_forbidden(
                "hypothesis → derived verlangt einen Beleg ANDERER Art — "
                f"'{additional.anchor}' ist wie der bestehende Beleg vom Kind "
                f"'{current.source_ref_kind.value}'."
            )

    async def create_edge(self, ctx: WorkspaceContext, data: KbEdgeCreate) -> KbEdgeRead:
        """Legt eine belegpflichtige Kante an — EINE Transaktion (Spec D).

        Ablauf: Timeline-Evidence-Gate fuer inhaltliche Kanten (Spec O §10.7,
        s. `_check_content_edge_evidence` — statisch, vor jedem DB-Zugriff),
        from/to aufloesen (mindestens eine Seite muss ein bestehender
        KB-Node sein; `from_node_id`/`to_node_id` werden gesetzt), JEDEN
        Evidence-Anker beider Seiten aufloesen (ein unaufloesbarer → 422 +
        vollstaendiger Rollback), Fallzahl-Gate fuer `co_occurs_with`
        (n < 20 → 422 mit tatsaechlichem n, VOR dem DB-CHECK), dann Edge +
        Evidence einfuegen. Bei `derived_from` UNIONen die Source-Areas des
        Parents (to-Seite) monoton ins Kind (from-Seite) — die Sichtbarkeit
        abgeleiteter Nodes wird nie breiter als ihre Quellen.
        """
        self._require_write(ctx, AgentCapability.kb_edge_write)
        _check_content_edge_evidence(data)
        restrict = await readable_area_ids(self._pool, ctx)
        async with self._pool.acquire() as conn, conn.transaction():
            from_res = await resolve_edge_end(
                self._repo, conn, ctx.workspace_id, data.from_anchor, restrict_area_ids=restrict
            )
            to_res = await resolve_edge_end(
                self._repo, conn, ctx.workspace_id, data.to_anchor, restrict_area_ids=restrict
            )
            if from_res.node_id is None and to_res.node_id is None:
                raise _no_node_side(data.from_anchor, data.to_anchor)
            for anchor in [*data.evidence_from, *data.evidence_to]:
                await resolve_anchor(
                    self._repo, conn, ctx.workspace_id, anchor, restrict_area_ids=restrict
                )
            if (
                data.type == EdgeType.co_occurs_with
                and data.co_n is not None
                and data.co_n < _CO_OCCURS_MIN_N
            ):
                raise _correlation_underpowered(data.co_n)
            edge = await self._repo.insert_edge(
                conn,
                ctx.workspace_id,
                edge_type=data.type.value,
                # Kanonische Anker-Form aus dem Resolver (L5) — `artifact:`-
                # Praefixe sind gestrippt, neighbors matcht dieselbe Form.
                from_anchor=from_res.anchor,
                to_anchor=to_res.anchor,
                from_node_id=from_res.node_id,
                to_node_id=to_res.node_id,
                co_query=data.co_query,
                co_n=data.co_n,
                co_from=data.co_from,
                co_to=data.co_to,
                created_by=self._actor(ctx),
            )
            await self._repo.insert_evidence(
                conn, ctx.workspace_id, edge.id, "from", list(data.evidence_from)
            )
            await self._repo.insert_evidence(
                conn, ctx.workspace_id, edge.id, "to", list(data.evidence_to)
            )
            if data.type == EdgeType.derived_from and from_res.node_id is not None:
                parent_areas: list[UUID] = []
                if to_res.node_id is not None:
                    parent_areas = await self._repo.source_areas(
                        conn, ctx.workspace_id, to_res.node_id
                    )
                elif to_res.area_id is not None:
                    parent_areas = [to_res.area_id]
                await self._repo.add_source_areas(
                    conn, ctx.workspace_id, from_res.node_id, parent_areas
                )
        node_sides = [nid for nid in (from_res.node_id, to_res.node_id) if nid is not None]
        await self._log_edge_node_writes(ctx, restrict, node_sides)
        return edge.model_copy(
            update={
                "evidence_from": list(data.evidence_from),
                "evidence_to": list(data.evidence_to),
            }
        )

    # ------------------------------------------------------------------- Reads

    async def get_node(self, ctx: WorkspaceContext, node_id: UUID) -> KbNodeRead | None:
        """Node im Sichtbarkeits-Scope; `None` = Router antwortet 404.

        Bewusst OHNE Kanten-Kontext (Spec O §10.7, WP18 — Modell-Freeze):
        wer die Kanten eines Nodes inkl. der Fallzahl `co_n` bei
        `co_occurs_with` braucht, fragt `neighbors` — dort ist die Fallzahl
        garantiert immer dabei.
        """
        restrict = await readable_area_ids(self._pool, ctx)
        node = await self._repo.get_node(
            self._pool, ctx.workspace_id, node_id, restrict_area_ids=restrict
        )
        if node is not None:
            await self._log_node(ctx, node.id, "read", node.sensitivity)
        return node

    # ------------------------------------------------------------- Zugriffslog

    async def _log_node(
        self, ctx: WorkspaceContext, node_id: UUID, operation: AccessOperation, sens: Sensitivity
    ) -> None:
        """Best-effort-Zugriffslog NACH erfolgreicher Operation (Spec F);
        `sens` ist der SERVER-Stand des Nodes, nie ein Client-Input."""
        await log_access(
            self._pool,
            ctx,
            ref_kind="node",
            ref_id=str(node_id),
            operation=operation,
            sensitivity=sens,
        )

    async def _log_edge_node_writes(
        self, ctx: WorkspaceContext, restrict: list[UUID] | None, node_ids: list[UUID]
    ) -> None:
        """Loggt ``(node, write)`` fuer die Node-Seiten einer neuen Kante.

        Die Sensitivity jeder Seite wird NACH dem Commit per Einzel-Read
        nachgeschlagen; der gesamte Block ist best-effort (Muster
        `access_log.log_access`) — auch ein Lookup-Fehler bricht den
        Kanten-Erfolg nie. Fuer Menschen-Tokens entfaellt alles ohne Query.
        """
        if ctx.agent_id is None:
            return
        try:
            for node_id in node_ids:
                node = await self._repo.get_node(
                    self._pool, ctx.workspace_id, node_id, restrict_area_ids=restrict
                )
                if node is not None:
                    await self._log_node(ctx, node.id, "write", node.sensitivity)
        except Exception:  # noqa: BLE001 — Logging bricht NIE den Hauptpfad
            logger.warning(
                "Zugriffslog fuer Kanten-Node-Seiten fehlgeschlagen (agent=%s)",
                ctx.agent_id,
                exc_info=True,
            )

    async def neighbors(
        self, ctx: WorkspaceContext, anchor: str, edge_type: EdgeType | None, depth: int
    ) -> list[KbNeighbor]:
        """Nachbar-Nodes eines Ankers bis Tiefe `depth` (1..3), nur sichtbare.

        Einstieg ist ein ``node:``- oder Artifact-Anker (422
        `anchor_unresolvable` sonst); ab Tiefe 2 laeuft die Traversierung
        ueber die Node-Frontier der Vorstufe. `co_n` traegt bei
        `co_occurs_with`-Kanten IMMER die Fallzahl (Spec-Akzeptanz O).
        """
        restrict = await readable_area_ids(self._pool, ctx)
        resolved = await resolve_edge_end(
            self._repo, self._pool, ctx.workspace_id, anchor, restrict_area_ids=restrict
        )
        type_value = edge_type.value if edge_type is not None else None
        results: list[KbNeighbor] = []
        seen: set[UUID] = set()
        if resolved.node_id is not None:
            seen.add(resolved.node_id)
            rows = await self._repo.adjacent_to_nodes(
                self._pool,
                ctx.workspace_id,
                [resolved.node_id],
                restrict_area_ids=restrict,
                edge_type=type_value,
            )
        else:
            rows = await self._repo.adjacent_to_anchor(
                self._pool,
                ctx.workspace_id,
                resolved.anchor,
                restrict_area_ids=restrict,
                edge_type=type_value,
            )
        for level in range(depth):
            frontier: list[UUID] = []
            for neighbor in rows:
                if neighbor.node.id in seen:
                    continue
                seen.add(neighbor.node.id)
                results.append(neighbor)
                frontier.append(neighbor.node.id)
            if level + 1 >= depth or not frontier:
                break
            rows = await self._repo.adjacent_to_nodes(
                self._pool,
                ctx.workspace_id,
                frontier,
                restrict_area_ids=restrict,
                edge_type=type_value,
            )
        return results

    async def search(self, ctx: WorkspaceContext, query: str, limit: int) -> list[KbSearchHit]:
        """KB-Suche: FTS ueber `kb_node.search` im Sichtbarkeits-Scope.

        Per Konstruktion NIE WorkArea-Inhalte (die Query liest nur
        `kb_node`); jeder Treffer traegt den Anker ``node:<id>``. Treffer
        sind NODES ohne Kanten-Kontext (Spec O §10.7, WP18): die
        `co_n`-Garantie fuer `co_occurs_with` liegt in `neighbors` — von
        einem Suchtreffer aus ist sie ueber dessen ``node:``-Anker einen
        Aufruf entfernt.
        """
        query = query.strip()
        if not query:
            return []
        restrict = await readable_area_ids(self._pool, ctx)
        return await self._repo.search(
            self._pool, ctx.workspace_id, query, limit, restrict_area_ids=restrict
        )

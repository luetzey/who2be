"""Promote: WorkArea-Artifact → Resource-DRAFT (ADR-0047, WP14 — Spec G).

Der EINE explizite Uebergang vom Rohmaterial (WorkArea) ins kuratierte Wissen
(Resource-Aggregat) — mit NULL Aenderung am Resource-Aggregat selbst: der
Service delegiert an den bestehenden `ResourceService` (Create- bzw.
Draft-Update-Pfad) und erzeugt IMMER einen Draft, nie eine aktive Version
(Spec-Akzeptanz G; aktiv schalten bleibt der menschliche Review-Schritt).

Gates (Reihenfolge wie `wa_artifacts.append`): erst die Lesbarkeit des
Artifacts (nicht lesbar = nicht existent → 404, kein Existenz-Leak), dann die
Resource-Gates via Delegation — `require_role(editor)` +
`require_capability(resource_write)` + `require_write_rate` liegen im
`ResourceService` (Promote ERZEUGT eine Resource; es gilt die bestehende
Capability, kein neues Vokabular).

Nur ``type='doc'``-Artifacts sind promotebar: blob/table tragen keinen
Block-Inhalt, aus dem eine Resource entstehen koennte. Der Fall ist ein
Aufrufer-Fehler ausserhalb der geschlossenen Problem-Taxonomie (weder
`ingest_unsupported` — kein Ingest — noch `anchor_unresolvable` — kein
Anker); er laeuft deshalb als Domain-Exception
(`PromoteUnsupportedArtifact`) ueber den generischen Validation-Weg des
Repos — der Router uebersetzt in ein sprechendes 422 (Muster
`wa_tables.TableRowsInvalid`).

Herkunft (Spec-Akzeptanz „die Resource traegt Artifact-ID und Zeitpunkt"):
`status_history`-Note via `StatusHistoryService.record` — das Schema (0012)
erlaubt ``from_status NULL``, der Eintrag lautet ``NULL → draft`` mit der
Provenance-Note. Beim Create traegt ZUSAETZLICH die Content-Description die
Herkunftszeile (sichtbar in der UI, ueberlebt Export/Duplikat); beim
Ziel-Update bleiben Description/Tags der Ziel-Resource unangetastet.

`status_history.changed_by` ist IMMER `ctx.user_id` (Security-Review Phase 2,
L3). Die Spalte referenziert einen USER; eine Agent-ID dort einzutragen
mischte zwei Identitaetsraeume in einer Spalte — Auswertungen ueber
`changed_by` (inkl. der GDPR-Anonymisierung in `purge_account_data`) wuerden
Agent-IDs fuer User-IDs halten. Die handelnde Maschine steht stattdessen als
``agent:<id>`` in der Note: dieselbe Information, im Freitextfeld, ohne den
Identitaetsraum der Spalte zu verletzen.

Zugriffslog (Spec F): der Promote LIEST das Artifact → ``(artifact, read)``.
KEIN Resource-Log — Resources sind kein WorkArea-Objekt, `agent_access_log`
protokolliert nur WorkArea/KB (`ref_kind artifact|node|table|blob`).

ARC-3: kein SQL, keine HTTPException — nur Domain-Exception, `ApiGateError`s
aus den delegierten Services, Repos und `core/workarea_scope`.
"""

from __future__ import annotations

import re
from uuid import UUID, uuid4

import asyncpg

from who2be_api.core.security import WorkspaceContext
from who2be_api.core.workarea_scope import artifact_not_found, readable_area_ids
from who2be_api.repositories.wa_artifact_repository import WaArtifactRepository
from who2be_api.services.access_log import log_access
from who2be_api.services.resource_service import ResourceService
from who2be_api.services.slug import slugify
from who2be_api.services.status_history_service import StatusHistoryService
from who2be_models import (
    ArtifactRead,
    ArtifactType,
    DocBlock,
    DocBlockKind,
    ResourceBlock,
    ResourceContent,
    ResourceCreate,
    ResourceRead,
    ResourceUpdate,
    VersionStatus,
)

# BlockNote-Heading-Level: der Editor kennt 1..3 — tiefere Markdown-Headings
# (h4–h6) werden auf 3 gekappt, damit die Insel den Block editieren kann.
_BLOCKNOTE_MAX_HEADING_LEVEL = 3

_HEADING_PREFIX_RE = re.compile(r"^#{1,6}\s+")

# Laengen-Deckel beim Uebergang Artifact → Resource (L4). Die beiden
# Aggregate haben UNTERSCHIEDLICHE Grenzen: `ArtifactCreate.title` erlaubt 300
# Zeichen, `ResourceCreate.name` nur 200 und `SlugStr` 100. Ohne die Schnitte
# erzeugt ein langer — voellig legitimer — Artifact-Titel eine
# ValidationError TIEF im Create-Pfad, die beim Aufrufer als 500 ankommt.
# Slug: 100 minus das Eindeutigkeits-Suffix `-<8 hex>` (9 Zeichen) ⇒ 90 mit Luft.
_SLUG_STEM_MAX_LENGTH = 90
_RESOURCE_NAME_MAX_LENGTH = 200

# Minimal-Props der Builder-Seeds (`builder_resource_conventions_body.json`) —
# BlockNote erwartet sie auf jedem Block; `ResourceBlock` ist extra="allow".
_DEFAULT_PROPS: dict[str, object] = {
    "textColor": "default",
    "backgroundColor": "default",
    "textAlignment": "left",
}


class PromoteUnsupportedArtifact(ValueError):
    """Nur doc-Artifacts sind promotebar — der Router antwortet 422.

    Domain-Exception statt HTTPException (ARC-3/DECISIONS 2026-07-20) und
    statt eines Taxonomie-Reasons (s. Modul-Kopf): blob-/table-Artifacts
    tragen keinen Block-Inhalt fuer eine Resource.
    """


def _blocks_to_blocknote(blocks: list[DocBlock]) -> list[dict[str, object]]:
    """Deterministischer Block→BlockNote-Konverter (pure Funktion, DB-los).

    Minimalform der echten Seeds (`builder_resource_conventions_body.json`):
    ``{id, type, props, content: [{type: 'text', text, styles: {}}],
    children: []}``. Headings uebernehmen `level` (auf BlockNote-1..3
    gekappt) und verlieren ihr ``#``-Praefix; paragraph/list/code werden
    paragraph-Blocks mit dem rohen Markdown als Text (Fences/Marker bleiben
    sichtbar — verlustfrei, der Mensch kuratiert im Draft). Die BlockNote-ID
    ist die stabile 8-stellige `block_id` des Artifacts — die Herkunft jedes
    Blocks bleibt damit bis auf Block-Ebene nachvollziehbar.
    """
    result: list[dict[str, object]] = []
    for block in blocks:
        if block.kind == DocBlockKind.heading:
            level = min(block.level or 1, _BLOCKNOTE_MAX_HEADING_LEVEL)
            text = _HEADING_PREFIX_RE.sub("", block.md).strip()
            block_type = "heading"
            props: dict[str, object] = {"level": level, **_DEFAULT_PROPS}
        else:
            text = block.md
            block_type = "paragraph"
            props = dict(_DEFAULT_PROPS)
        result.append(
            {
                "id": block.block_id,
                "type": block_type,
                "props": props,
                "content": [{"type": "text", "text": text, "styles": {}}],
                "children": [],
            }
        )
    return result


def _provenance_note(artifact: ArtifactRead, agent_id: UUID | None = None) -> str:
    """Herkunfts-Note: Artifact-ID + fachlicher Zeitpunkt (Spec-Akzeptanz G).

    Mit `agent_id` haengt die handelnde Maschine als ``agent:<id>`` an (L3,
    s. Modul-Kopf) — die `status_history`-Spalte `changed_by` bleibt dem
    User-Identitaetsraum vorbehalten.
    """
    note = (
        f"Promotet aus wa_artifact {artifact.id} "
        f"({artifact.occurred_at.isoformat()}), Quelle WorkArea."
    )
    return f"{note} (agent:{agent_id})" if agent_id is not None else note


class WaPromoteService:
    """Promote-Orchestrierung: WorkArea lesen, Resource-Draft schreiben."""

    def __init__(
        self,
        pool: asyncpg.Pool,
        artifact_repo: WaArtifactRepository,
        resource_service: ResourceService,
        history: StatusHistoryService,
    ) -> None:
        self._pool = pool
        self._artifacts = artifact_repo
        self._resources = resource_service
        self._history = history

    async def promote_artifact(
        self,
        ctx: WorkspaceContext,
        artifact_id: UUID,
        target_resource_id: UUID | None = None,
    ) -> ResourceRead:
        """Promotet ein doc-Artifact zu einer Resource-DRAFT (nie Active).

        Ohne `target_resource_id` entsteht eine NEUE Resource (Draft v1,
        `ResourceService.create` — Editor-Gate + `resource_write` + Rate).
        Der Slug bekommt ein eindeutiges Suffix (Muster
        `ResourceService.duplicate`): ein Promote darf nicht an einer
        Slug-Kollision mit unabhaengigen Resources scheitern, und jeder
        Promote erzeugt bewusst eine eigene neue Resource.

        Mit `target_resource_id` ersetzt der Draft-Pfad
        (`ResourceService.update_draft`) die Bloecke der bestehenden
        Resource; Description/Tags der Ziel-Resource bleiben erhalten. Ein
        bestehender Review-Konflikt propagiert als 409 (`review_pending`),
        eine unsichtbare/fremde Ziel-Resource als 404.
        """
        restrict = await readable_area_ids(self._pool, ctx)
        artifact = await self._artifacts.get(
            self._pool,
            ctx.workspace_id,
            artifact_id,
            restrict_area_ids=restrict,
            include_blocks=True,
        )
        if artifact is None:
            raise artifact_not_found()
        if artifact.type != ArtifactType.doc:
            raise PromoteUnsupportedArtifact(
                f"Nur doc-Artifacts sind promotebar — dieses Artifact ist "
                f"'{artifact.type.value}'. blob/table tragen keinen Block-Inhalt; "
                "fuer Tabellen-Auswertungen erst `save_query_result` nutzen."
            )

        raw_blocks = _blocks_to_blocknote(artifact.blocks or [])
        blocks = [ResourceBlock.model_validate(block) for block in raw_blocks]

        if target_resource_id is None:
            resource = await self._create_resource(ctx, artifact, blocks)
        else:
            resource = await self._update_target(ctx, target_resource_id, blocks)

        await self._record_provenance(ctx, artifact, resource)
        # Zugriffslog (Spec F): der Promote hat das Artifact GELESEN; die
        # Resource ist kein WorkArea-Objekt und wird nicht geloggt.
        await log_access(
            self._pool,
            ctx,
            ref_kind="artifact",
            ref_id=str(artifact.id),
            operation="read",
            sensitivity=artifact.sensitivity,
        )
        return resource

    async def _create_resource(
        self, ctx: WorkspaceContext, artifact: ArtifactRead, blocks: list[ResourceBlock]
    ) -> ResourceRead:
        """Neue Resource als Draft v1 — Herkunftszeile in der Description.

        Name und Slug werden auf die Resource-Grenzen gekuerzt (L4): der
        Artifact-Titel darf laenger sein als beide. Ein am Schnitt
        entstandener Rand-Bindestrich faellt weg, damit die `SlugStr`-Form
        (`^[a-z0-9][a-z0-9-]*$`) erhalten bleibt; ein leerer Rest faellt auf
        `slugify`s Fallback zurueck.
        """
        content = ResourceContent(
            description=_provenance_note(artifact),
            blocks=blocks,
            tags=[],
        )
        stem = slugify(artifact.title)[:_SLUG_STEM_MAX_LENGTH].strip("-") or slugify("")
        slug = f"{stem}-{uuid4().hex[:8]}"
        name = artifact.title[:_RESOURCE_NAME_MAX_LENGTH].strip() or artifact.title[:1]
        return await self._resources.create(
            ctx, ResourceCreate(name=name, slug=slug, content=content)
        )

    async def _update_target(
        self, ctx: WorkspaceContext, target_resource_id: UUID, blocks: list[ResourceBlock]
    ) -> ResourceRead:
        """Draft-Update der Ziel-Resource: Bloecke ersetzen, Metadaten erhalten."""
        target = await self._resources.get(ctx, target_resource_id)
        content = ResourceContent(
            description=target.content.description,
            blocks=blocks,
            tags=target.content.tags,
        )
        return await self._resources.update_draft(
            ctx, target_resource_id, ResourceUpdate(content=content)
        )

    async def _record_provenance(
        self, ctx: WorkspaceContext, artifact: ArtifactRead, resource: ResourceRead
    ) -> None:
        """Herkunfts-Note in `status_history` (append-only, Migration 0012).

        ``from_status`` ist im Schema nullable — der Eintrag lautet
        ``NULL → draft`` auf der promoteten Version (Create: v1; Ziel-Update:
        die Draft-Version = `current_version` nach `upsert_draft`). Der
        Create-Pfad des Resource-Aggregats schreibt selbst keine History
        (nur Transitions), darum liegt die Provenance-Zeile hier.

        `changed_by` ist der USER (L3) — auch im Agent-Pfad; die Agent-ID
        steht in der Note.
        """
        async with self._pool.acquire() as conn:
            await self._history.record(
                conn,
                "resource",
                resource.id,
                None,
                VersionStatus.draft,
                ctx.user_id,
                _provenance_note(artifact, ctx.agent_id),
                version=resource.current_version,
            )

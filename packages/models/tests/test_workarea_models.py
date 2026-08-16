"""Unit-Tests fuer die WorkArea-Models (WP1, ADR-0047).

DB-frei: Roundtrips + die Modell-Validatoren (Schatten-System-Schutz,
Patch-Op-Pflichten, genau-eins-von url/file_b64, DocBlock-Level-Regel).
Die serverseitige Durchsetzung (Area-Grants, rev-Konflikt, Ingest-Limits)
lebt in den API-WPs.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from who2be_models import (
    ArtifactAppend,
    ArtifactCreate,
    ArtifactMarkdown,
    ArtifactPatch,
    ArtifactRead,
    ArtifactType,
    DocBlock,
    DocBlockKind,
    IngestRequest,
    IngestResult,
    OccurredPrecision,
    Sensitivity,
    TimelineResult,
    TimelineSlice,
    WorkAreaAssignment,
    WorkAreaCreate,
    WorkAreaGrantLevel,
    WorkAreaGrantRead,
    WorkAreaGrantSet,
    WorkAreaRead,
    WorkAreaScope,
    WorkAreaSearchHit,
)

_NOW = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)


class TestWorkArea:
    def test_create_minimal_and_roundtrip(self) -> None:
        area = WorkAreaCreate(name="Recherche")
        assert area.retention_days is None
        assert WorkAreaCreate.model_validate(area.model_dump()) == area

    def test_create_rejects_nonpositive_retention(self) -> None:
        with pytest.raises(ValidationError):
            WorkAreaCreate(name="x", retention_days=0)

    def test_create_forbids_extra_fields(self) -> None:
        # `scope` ist bewusst KEIN Create-Feld: explizit angelegt werden nur
        # shared Areas; private entstehen automatisch beim ersten Zugriff.
        with pytest.raises(ValidationError):
            WorkAreaCreate.model_validate({"name": "x", "scope": "private"})

    def test_read_roundtrip(self) -> None:
        read = WorkAreaRead.model_validate(
            {
                "id": uuid4(),
                "workspace_id": uuid4(),
                "scope": "private",
                "owner_agent_id": uuid4(),
                "name": "Privat",
                "retention_days": None,
                "created_at": _NOW,
                "updated_at": _NOW,
            }
        )
        assert read.scope == WorkAreaScope.private

    def test_grant_set_and_read(self) -> None:
        assert WorkAreaGrantSet(level=WorkAreaGrantLevel.write).level == "write"
        grant = WorkAreaGrantRead.model_validate(
            {"area_id": uuid4(), "agent_id": uuid4(), "level": "read", "created_at": _NOW}
        )
        assert grant.level == WorkAreaGrantLevel.read

    def test_assignment_shape_for_whoami(self) -> None:
        assignment = WorkAreaAssignment.model_validate(
            {"id": uuid4(), "name": "Team", "scope": "shared", "level": "write"}
        )
        assert assignment.scope == WorkAreaScope.shared


class TestDocBlock:
    def test_heading_with_level_ok(self) -> None:
        block = DocBlock(block_id="a1b2c3d4", kind=DocBlockKind.heading, level=2, md="## Titel")
        assert block.level == 2

    def test_level_forbidden_for_non_heading(self) -> None:
        with pytest.raises(ValidationError, match="heading"):
            DocBlock(block_id="a1b2c3d4", kind=DocBlockKind.paragraph, level=1, md="Text")

    def test_block_id_must_be_eight_chars(self) -> None:
        with pytest.raises(ValidationError):
            DocBlock(block_id="kurz", kind=DocBlockKind.paragraph, md="Text")


class TestArtifactCreate:
    def test_defaults(self) -> None:
        artifact = ArtifactCreate(title="Notiz", occurred_at=_NOW)
        assert artifact.content_md == ""
        assert artifact.occurred_precision == OccurredPrecision.minute
        assert artifact.sensitivity == Sensitivity.general
        assert artifact.source_system is None

    def test_source_system_requires_fetched_at(self) -> None:
        # Schatten-System-Schutz (Spec §3): Fremdsystem-Daten ohne
        # Abrufzeitpunkt sind abgelehnt.
        with pytest.raises(ValidationError, match="fetched_at"):
            ArtifactCreate(title="Export", occurred_at=_NOW, source_system="bank-api")

    def test_source_system_with_fetched_at_ok(self) -> None:
        artifact = ArtifactCreate(
            title="Export",
            occurred_at=_NOW,
            source_system="bank-api",
            fetched_at=_NOW,
        )
        assert artifact.fetched_at == _NOW

    def test_forbids_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactCreate.model_validate({"title": "x", "occurred_at": _NOW, "rev": 2})


class TestArtifactPatch:
    def test_replace_requires_content(self) -> None:
        with pytest.raises(ValidationError, match="content_md"):
            ArtifactPatch(anchor="a1b2c3d4", op="replace", expected_rev=1)

    def test_insert_after_requires_content(self) -> None:
        with pytest.raises(ValidationError, match="content_md"):
            ArtifactPatch(anchor="a1b2c3d4", op="insert_after", expected_rev=3)

    def test_delete_without_content_ok(self) -> None:
        patch = ArtifactPatch(anchor="a1b2c3d4", op="delete", expected_rev=2)
        assert patch.content_md is None

    def test_expected_rev_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactPatch(
                anchor="a1b2c3d4",
                op="replace",
                content_md="Neu",
                expected_rev=0,
            )

    def test_append_requires_content(self) -> None:
        with pytest.raises(ValidationError):
            ArtifactAppend(content_md="")
        assert ArtifactAppend(content_md="Mehr Text").content_md == "Mehr Text"


class TestArtifactRead:
    def test_doc_roundtrip_with_blocks(self) -> None:
        read = ArtifactRead.model_validate(
            {
                "id": uuid4(),
                "area_id": uuid4(),
                "workspace_id": uuid4(),
                "type": "doc",
                "title": "Notiz",
                "rev": 3,
                "occurred_at": _NOW,
                "occurred_precision": "minute",
                "sensitivity": "general",
                "created_at": _NOW,
                "updated_at": _NOW,
                "updated_by": "agent:00000000-0000-0000-0000-000000000001",
                "blocks": [{"block_id": "a1b2c3d4", "kind": "paragraph", "md": "Text"}],
            }
        )
        assert read.type == ArtifactType.doc
        assert read.blocks is not None and read.blocks[0].kind == DocBlockKind.paragraph
        assert read.blob_sha256 is None

    def test_markdown_read_shape(self) -> None:
        markdown = ArtifactMarkdown.model_validate(
            {"artifact_id": uuid4(), "title": "Notiz", "rev": 1, "markdown": "[#a1b2c3d4] Text"}
        )
        assert markdown.rev == 1


class TestIngest:
    def test_exactly_one_source_url(self) -> None:
        request = IngestRequest(url="https://example.org/doc.pdf")
        assert request.file_b64 is None

    def test_exactly_one_source_file(self) -> None:
        request = IngestRequest(file_b64="aGFsbG8=", filename="notiz.txt")
        assert request.url is None

    def test_both_sources_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Genau eine Quelle"):
            IngestRequest(url="https://example.org/x", file_b64="aGFsbG8=")

    def test_no_source_rejected(self) -> None:
        with pytest.raises(ValidationError, match="Genau eine Quelle"):
            IngestRequest()

    def test_result_roundtrip(self) -> None:
        result = IngestResult.model_validate(
            {
                "blob_artifact_id": uuid4(),
                "doc_artifact_id": uuid4(),
                "sha256": "ab" * 32,
                "deduplicated": True,
                "block_count": 12,
            }
        )
        assert result.deduplicated is True


class TestSearchAndTimeline:
    def test_search_hit_roundtrip(self) -> None:
        artifact_id = uuid4()
        hit = WorkAreaSearchHit.model_validate(
            {
                "anchor": f"{artifact_id}#a1b2c3d4",
                "artifact_id": artifact_id,
                "block_id": "a1b2c3d4",
                "title": "Notiz",
                "snippet": "…Text…",
                "score": 0.42,
                "area_id": uuid4(),
            }
        )
        assert hit.anchor.endswith("#a1b2c3d4")

    def test_timeline_result_defaults_and_unknown_bucket(self) -> None:
        empty = TimelineResult()
        assert empty.slices == [] and empty.unknown == []
        result = TimelineResult.model_validate(
            {
                "slices": [
                    {
                        "bucket": "2026-08-13",
                        "items": [{"anchor": "x#y", "kind": "artifact"}],
                        "counts": {"artifact": 1},
                    }
                ],
                "unknown": [{"anchor": "z#w", "kind": "node"}],
            }
        )
        assert isinstance(result.slices[0], TimelineSlice)
        assert result.unknown[0].kind == "node"

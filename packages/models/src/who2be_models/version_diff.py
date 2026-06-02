"""Strukturierter Versions-Diff (Track A: Versionierung-Core).

Read-only Ausgabe von `GET .../versions/{n}/diff?against=active`: ein flacher,
serverseitig berechneter Feld-/Block-Diff zweier Versions-Inhalte. Die UI
rendert die `changes`-Liste ohne weitere Logik. `before` ist der Vergleichs-
Stand (z. B. die aktive Version), `after` die betrachtete Version `n`.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DiffOp = Literal["added", "removed", "changed"]


class VersionDiffChange(BaseModel):
    """Eine einzelne Aenderung im Versions-Diff.

    `path` ist ein punkt-/klammer-separierter Pfad in den Content-JSON
    (`description`, `tags`, `content.blocks[<block-id>]`). Block-Listen werden
    per stabiler Block-`id` gematcht, sodass das Verschieben eines Blocks nicht
    als Massen-Aenderung erscheint.
    """

    model_config = ConfigDict(from_attributes=True)

    path: str
    op: DiffOp
    before: Any = None
    after: Any = None


class VersionDiff(BaseModel):
    """Strukturierter Diff einer Version gegen einen Vergleichsstand."""

    model_config = ConfigDict(from_attributes=True)

    version: int
    against: str
    against_version: int | None = None
    changes: list[VersionDiffChange] = Field(default_factory=list)
    identical: bool = True

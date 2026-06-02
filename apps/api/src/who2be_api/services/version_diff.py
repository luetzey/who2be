"""Serverseitiger, generischer Versions-Diff (Track A: Versionierung-Core).

Vergleicht zwei Content-JSON-Snapshots (das jsonb-Feld einer Version) und
liefert eine flache `VersionDiffChange`-Liste. Bewusst entity-agnostisch: die
Funktion kennt weder Persona- noch Playbook-Felder, sondern walked die
Dicts generisch. BlockNote-Block-Listen (Listen aus Dicts mit `id`) werden
ueber die stabile Block-`id` gematcht, damit eine Umsortierung nicht als
Massen-Aenderung erscheint.
"""

from typing import Any

from who2be_models import VersionDiff, VersionDiffChange

# Sentinel fuer „Schluessel auf dieser Seite nicht vorhanden" — unterscheidet
# `fehlt` von `ist None`/`ist []`.
_MISSING: Any = object()


def _is_block_list(value: Any) -> bool:
    """True wenn `value` eine nicht-leere Liste aus Bloecken (Dict mit `id`) ist."""
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(isinstance(item, dict) and "id" in item for item in value)
    )


def _list_like(value: Any) -> bool:
    """True wenn `value` als Block-Listen-Seite zaehlt (Liste, None oder fehlend)."""
    return isinstance(value, list) or value is None or value is _MISSING


def _diff_block_list(
    path: str, before: list[Any], after: list[Any], changes: list[VersionDiffChange]
) -> None:
    before_by_id = {block["id"]: block for block in before if isinstance(block, dict)}
    after_by_id = {block["id"]: block for block in after if isinstance(block, dict)}
    # Stabile Reihenfolge: erst die Before-IDs (Dokument-Reihenfolge), dann
    # neu hinzugekommene IDs aus After.
    ordered_ids = list(before_by_id)
    ordered_ids.extend(bid for bid in after_by_id if bid not in before_by_id)
    for bid in ordered_ids:
        before_block = before_by_id.get(bid, _MISSING)
        after_block = after_by_id.get(bid, _MISSING)
        item_path = f"{path}[{bid}]"
        if before_block is _MISSING:
            changes.append(
                VersionDiffChange(path=item_path, op="added", before=None, after=after_block)
            )
        elif after_block is _MISSING:
            changes.append(
                VersionDiffChange(path=item_path, op="removed", before=before_block, after=None)
            )
        elif before_block != after_block:
            changes.append(
                VersionDiffChange(
                    path=item_path, op="changed", before=before_block, after=after_block
                )
            )


def _diff_value(
    path: str, before: Any, after: Any, changes: list[VersionDiffChange]
) -> None:
    if before is _MISSING and after is _MISSING:
        return
    if before is not _MISSING and after is not _MISSING and before == after:
        return

    # Beide Seiten Dicts → rekursiv pro Schluessel.
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            child_path = f"{path}.{key}" if path else key
            _diff_value(child_path, before.get(key, _MISSING), after.get(key, _MISSING), changes)
        return

    # Block-Listen (Listen aus Dicts mit `id`) → ID-gematchter Block-Diff.
    if (_is_block_list(before) or _is_block_list(after)) and _list_like(before) and _list_like(
        after
    ):
        before_list = before if isinstance(before, list) else []
        after_list = after if isinstance(after, list) else []
        _diff_block_list(path, before_list, after_list, changes)
        return

    # Skalar / Nicht-Block-Liste / Typ-Wechsel → ganzer Wert.
    if before is _MISSING:
        changes.append(VersionDiffChange(path=path, op="added", before=None, after=after))
    elif after is _MISSING:
        changes.append(VersionDiffChange(path=path, op="removed", before=before, after=None))
    else:
        changes.append(VersionDiffChange(path=path, op="changed", before=before, after=after))


def compute_version_diff(
    *,
    version: int,
    against: str,
    against_version: int | None,
    before: dict[str, Any],
    after: dict[str, Any],
) -> VersionDiff:
    """Berechnet den strukturierten Diff `before → after`.

    `before` ist der Vergleichsstand (z. B. die aktive Version), `after` die
    betrachtete Version `version`. Ohne Vergleichsstand (`against_version=None`)
    erscheint der gesamte Inhalt von `after` als `added`.
    """
    changes: list[VersionDiffChange] = []
    _diff_value("", before, after, changes)
    return VersionDiff(
        version=version,
        against=against,
        against_version=against_version,
        changes=changes,
        identical=len(changes) == 0,
    )


__all__ = ["compute_version_diff"]

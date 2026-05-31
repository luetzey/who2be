"""Promote-Validation fuer Status-Wechsel `draft -> review` / `draft -> active`.

Prueft, ob alle Pflichtfelder einer Version ausgefuellt sind, bevor sie
promoted werden kann. Wirft `PromoteValidationError(missing=[...])`, wenn
mindestens ein Pflichtfeld leer ist.

Pflichtfeld-Tabelle (Welle 4, Spec):
  persona  -> name, description, body (content.blocks nicht leer)
  playbook -> name, description, body, type
  resource -> name, description, body (blocks nicht leer)
  agent    -> n/a (kein Versions-Workflow; Agents nutzen enabled/disabled)

„Leer" = leerer String oder None. Tags und Properties sind NICHT Pflicht.

Wird aufgerufen in den Transition-Endpunkten unmittelbar nach der
State-Machine-Pruefung (validate_transition) und vor dem DB-UPDATE, aber
nur fuer die Promote-Richtungen draft -> review und draft -> active.
"""

from typing import Any

from who2be_models import VersionStatus


class PromoteValidationError(Exception):
    """Wirft bei fehlendem Pflichtfeld waehrend Promote.

    `missing` enthaelt die Feldnamen aus der Entity-Pflichtfeld-Tabelle,
    die leer oder None sind.
    """

    def __init__(self, missing: list[str]) -> None:
        super().__init__(f"Promote-Pflichtfelder fehlen: {', '.join(missing)}")
        self.missing = missing


def _is_promote(to_status: VersionStatus) -> bool:
    """True wenn der Ziel-Status eine Promotion aus Draft heraus ist."""
    return to_status in (VersionStatus.review, VersionStatus.active)


def _field_empty(value: Any) -> bool:
    """True wenn `value` als 'leer' gilt (None oder leerer String)."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _blocks_empty(blocks: list[Any]) -> bool:
    """True wenn die Bloeckliste als 'kein Body' gilt.

    Leere Liste = kein Inhalt. Eine Liste mit nur leeren Paragraph-Bloecken
    gilt ebenfalls als leer. Regeln:
    - Nicht-dict Elemente: konservativ als befuellt werten.
    - Block ohne 'content'-Schluessel (z. B. Image, Divider): konservativ
      als befuellt werten — non-text Bloecke sind valider Inhalt.
    - Block mit 'content'-Liste: leer wenn alle Items keinen sichtbaren Text
      tragen.
    """
    if not blocks:
        return True
    for block in blocks:
        if not isinstance(block, dict):
            # Unbekanntes Format — konservativ als befuellt werten.
            return False
        if "content" not in block:
            # Non-text-Block (Image, HorizontalRule, …) — konservativ befuellt.
            return False
        content_items = block.get("content", [])
        if isinstance(content_items, list):
            for item in content_items:
                if isinstance(item, dict):
                    text = item.get("text", "")
                    if isinstance(text, str) and text.strip():
                        return False
    return True


def validate_promote_persona(
    name: str,
    content: dict[str, Any],
    to_status: VersionStatus,
) -> None:
    """Prueft Persona-Pflichtfelder vor Promote.

    `content` ist das deserialisierte `persona_version.content`-JSONB.
    Pflichtfelder: name, description, body (content.content.blocks nicht leer).
    """
    if not _is_promote(to_status):
        return
    missing: list[str] = []
    if _field_empty(name):
        missing.append("name")
    description = content.get("description", "")
    if _field_empty(description):
        missing.append("description")
    # Body = blocks im verschachtelten PersonaContent-Objekt (content.content.blocks)
    inner = content.get("content") or {}
    blocks = inner.get("blocks", []) if isinstance(inner, dict) else []
    if _blocks_empty(blocks):
        missing.append("body")
    if missing:
        raise PromoteValidationError(missing)


def validate_promote_playbook(
    name: str,
    content: dict[str, Any],
    to_status: VersionStatus,
) -> None:
    """Prueft Playbook-Pflichtfelder vor Promote.

    `content` ist das deserialisierte `playbook_version.content`-JSONB.
    Pflichtfelder: name, description, body, type.
    """
    if not _is_promote(to_status):
        return
    missing: list[str] = []
    if _field_empty(name):
        missing.append("name")
    if _field_empty(content.get("description", "")):
        missing.append("description")
    if _field_empty(content.get("body", "")):
        missing.append("body")
    if _field_empty(content.get("type", "")):
        missing.append("type")
    if missing:
        raise PromoteValidationError(missing)


def validate_promote_resource(
    name: str,
    content: dict[str, Any],
    to_status: VersionStatus,
) -> None:
    """Prueft Resource-Pflichtfelder vor Promote.

    `content` ist das deserialisierte `resource_version.content`-JSONB.
    Pflichtfelder: name, description, body (blocks nicht leer).
    """
    if not _is_promote(to_status):
        return
    missing: list[str] = []
    if _field_empty(name):
        missing.append("name")
    if _field_empty(content.get("description", "")):
        missing.append("description")
    blocks = content.get("blocks", [])
    if _blocks_empty(blocks):
        missing.append("body")
    if missing:
        raise PromoteValidationError(missing)


__all__ = [
    "PromoteValidationError",
    "validate_promote_persona",
    "validate_promote_playbook",
    "validate_promote_resource",
]

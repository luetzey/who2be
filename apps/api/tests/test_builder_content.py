"""Tests fuer `builder_content.py` (WP7 Teil 1 — Content-Packs pro Sprache).

Reine Modul-Tests (kein DB-Zugriff): pruefen die Struktur-Invarianten der
Packs (Cross-Locale-Schluessel-Parallelitaet, Trigger-Disjunktheit,
Sidecar-Existenz/-Parsbarkeit) und den Fehlerfall fuer nicht unterstuetzte
Sprachen. Die eigentliche Verdrahtung (Seeding/Sync liest ueber
`get_content_pack`) ist WP8 vorbehalten — `workspace_repository.py` bleibt
hier unangetastet.
"""

from __future__ import annotations

import json
from collections.abc import Iterable

import pytest

from who2be_api.repositories.builder_content import (
    SUPPORTED_LOCALES,
    ContentPack,
    get_content_pack,
    load_sidecar,
)

_DE_PACK = get_content_pack("de")
_EN_PACK = get_content_pack("en")

# EN-Sidecars, die laut WP7-Aufteilung PARALLEL von anderen Agents erzeugt
# werden und zum Zeitpunkt dieses Teils (Teil 1) noch fehlen koennen. TODO:
# schaerfen sobald alle EN-Sidecars liegen (dann feste Existenz-Assertions
# statt der `skip_if_missing`-Toleranz unten; siehe Plan WP7).
_EN_SIDECARS_PENDING = {
    "builder_persona_content.json",
    "builder_persona_modes.json",
    "builder_resource_conventions_body.json",
    "builder_playbook_agent_body.json",
    "builder_playbook_persona_body.json",
    "builder_playbook_consistency_body.json",
    "builder_playbook_playbook_body.json",
    "builder_playbook_maintenance_body.json",
}


def _en_sidecar_path(filename: str) -> str:
    from pathlib import Path

    return str(Path(__file__).parent.parent / "src/who2be_api/repositories/en" / filename)


def test_supported_locales_expose_de_and_en() -> None:
    assert SUPPORTED_LOCALES == ("de", "en")


def test_get_content_pack_unsupported_locale_raises_value_error() -> None:
    with pytest.raises(ValueError, match="fr"):
        get_content_pack("fr")


def test_get_content_pack_returns_contentpack_instances() -> None:
    assert isinstance(_DE_PACK, ContentPack)
    assert isinstance(_EN_PACK, ContentPack)
    assert _DE_PACK.locale == "de"
    assert _EN_PACK.locale == "en"


def test_template_slugs_match_across_locales_in_order() -> None:
    """Slug = stabiler Cross-Locale-Schluessel; Reihenfolge muss identisch sein."""
    de_slugs = [t.slug for t in _DE_PACK.templates]
    en_slugs = [t.slug for t in _EN_PACK.templates]
    assert de_slugs == en_slugs
    assert de_slugs == [
        "customer-support-agent",
        "knowledge-worker",
        "conversational-coach",
        "workflow-starter",
        "agent-builder",
        "agent-builder-lite",
    ]


def test_playbook_keys_match_across_locales_in_order() -> None:
    """key = stabiler Cross-Locale-Schluessel je Builder-Playbook."""
    de_keys = [p.key for p in _DE_PACK.playbooks]
    en_keys = [p.key for p in _EN_PACK.playbooks]
    assert de_keys == en_keys
    assert de_keys == [
        "persona",
        "playbook",
        "agent",
        "consistency",
        "maintenance",
        "external_tool",
    ]


def test_resource_slug_is_locale_invariant() -> None:
    """Der Resource-Slug ist rein technisch und bleibt ueber Sprachen identisch."""
    assert _DE_PACK.resource.slug == _EN_PACK.resource.slug == "agent-bau-konventionen"


def test_persona_name_builder_stays_untranslated() -> None:
    assert _DE_PACK.persona.name == "Builder"
    assert _EN_PACK.persona.name == "Builder"


def test_sidecar_filenames_match_across_locales() -> None:
    """Gleicher Dateiname in beiden Sprachen (nur der Ordner-Praefix wechselt)."""
    assert [t.sidecar for t in _DE_PACK.templates] == [t.sidecar for t in _EN_PACK.templates]
    assert _DE_PACK.persona.content_sidecar == _EN_PACK.persona.content_sidecar
    assert _DE_PACK.persona.modes_sidecar == _EN_PACK.persona.modes_sidecar
    assert [p.sidecar for p in _DE_PACK.playbooks] == [p.sidecar for p in _EN_PACK.playbooks]
    assert _DE_PACK.resource.sidecar == _EN_PACK.resource.sidecar


def _assert_triggers_disjoint(pack: ContentPack) -> None:
    """Trigger-Disjunktheit je Pack (Plan WP7 §5): jede einzelne Trigger-Phrase
    (kommasepariertes Item) darf in genau einem der sechs Builder-Playbooks
    vorkommen — analog der DE-Hygiene (`workspace_repository.py` ~Zeile 410:
    keine domaenen-uebergreifend kollidierenden Trigger)."""
    seen: dict[str, str] = {}
    for playbook in pack.playbooks:
        phrases: Iterable[str] = (p.strip() for p in playbook.triggers.split(","))
        for phrase in phrases:
            assert phrase, f"Leere Trigger-Phrase in Playbook {playbook.key!r}"
            other = seen.get(phrase)
            assert other is None, (
                f"Trigger-Phrase {phrase!r} kollidiert zwischen "
                f"Playbook {other!r} und {playbook.key!r} (Pack {pack.locale!r})"
            )
            seen[phrase] = playbook.key


def test_trigger_phrases_disjoint_de_pack() -> None:
    _assert_triggers_disjoint(_DE_PACK)


def test_trigger_phrases_disjoint_en_pack() -> None:
    _assert_triggers_disjoint(_EN_PACK)


def test_playbook_types_and_tags_present_for_all_playbooks() -> None:
    for pack in (_DE_PACK, _EN_PACK):
        for playbook in pack.playbooks:
            assert playbook.type in {"workflow", "checklist"}
            assert playbook.tags
            assert playbook.description


@pytest.mark.parametrize(
    "filename",
    [
        "customer_support_body.json",
        "knowledge_worker_body.json",
        "conversational_coach_body.json",
        "workflow_starter_body.json",
        "agent_builder_body.json",
        "agent_builder_lite_body.json",
        "builder_persona_content.json",
        "builder_persona_modes.json",
        "builder_playbook_persona_body.json",
        "builder_playbook_playbook_body.json",
        "builder_playbook_agent_body.json",
        "builder_playbook_consistency_body.json",
        "builder_playbook_maintenance_body.json",
        "builder_playbook_external_tool_body.json",
        "builder_resource_conventions_body.json",
    ],
)
def test_de_sidecars_exist_and_parse(filename: str) -> None:
    """DE-Sidecars liegen alle flach vor (unveraendert) und sind valides JSON."""
    raw = load_sidecar(filename, "de")
    parsed = json.loads(raw)
    assert parsed  # nicht-leeres Array/Objekt


@pytest.mark.parametrize(
    "filename",
    [
        "customer_support_body.json",
        "knowledge_worker_body.json",
        "conversational_coach_body.json",
        "workflow_starter_body.json",
        "agent_builder_body.json",
        "agent_builder_lite_body.json",
        "builder_persona_content.json",
        "builder_persona_modes.json",
        "builder_playbook_persona_body.json",
        "builder_playbook_playbook_body.json",
        "builder_playbook_agent_body.json",
        "builder_playbook_consistency_body.json",
        "builder_playbook_maintenance_body.json",
        "builder_playbook_external_tool_body.json",
        "builder_resource_conventions_body.json",
    ],
)
def test_en_sidecars_exist_and_parse_when_present(filename: str) -> None:
    """EN-Sidecars: nur pruefen, wenn schon vorhanden.

    Sieben der 14 EN-Sidecars werden GLEICHZEITIG von anderen Agents dieses
    WP7-Durchlaufs erzeugt (siehe `_EN_SIDECARS_PENDING`) und koennen zum
    Zeitpunkt dieses Tests noch fehlen — kein Fehlschlag, sondern `skip`.
    TODO: schaerfen (Toleranz entfernen) sobald alle EN-Sidecars liegen.
    """
    from pathlib import Path

    if not Path(_en_sidecar_path(filename)).exists():
        if filename in _EN_SIDECARS_PENDING:
            pytest.skip(f"EN-Sidecar {filename!r} noch nicht uebersetzt (parallele WP7-Arbeit)")
        pytest.fail(f"EN-Sidecar {filename!r} fehlt unerwartet (nicht in _EN_SIDECARS_PENDING)")
    raw = load_sidecar(filename, "en")
    parsed = json.loads(raw)
    assert parsed


def test_en_pack_display_texts_are_translated_not_de_literals() -> None:
    """Stichprobe: EN-Anzeigetexte sind nicht einfach die DE-Strings (echte
    Uebersetzung statt Kopie) — ausser dem bewusst untranslated Persona-Namen."""
    de_template_names = {t.name for t in _DE_PACK.templates}
    en_template_names = {t.name for t in _EN_PACK.templates}
    assert de_template_names.isdisjoint(en_template_names)

    assert _DE_PACK.persona.description != _EN_PACK.persona.description
    assert set(_DE_PACK.persona.traits).isdisjoint(_EN_PACK.persona.traits)

    de_playbook_names = {p.name for p in _DE_PACK.playbooks}
    en_playbook_names = {p.name for p in _EN_PACK.playbooks}
    assert de_playbook_names.isdisjoint(en_playbook_names)

    assert _DE_PACK.resource.name != _EN_PACK.resource.name
    assert _EN_PACK.resource.name == "Agent-Building Conventions"

    assert _DE_PACK.agent.description != _EN_PACK.agent.description
    assert _DE_PACK.agent_lite.description != _EN_PACK.agent_lite.description


# Sprach-Formulierungen, die auf eine (verbotene) eigene Sprachanweisung im
# Template-Body hindeuten — Heuristik analog dem urspruenglichen Widerspruch
# `ab-p8`/`cs-p6` ("...nutze die gleiche Sprache wie der Nutzer." neben der
# harten Renderer-Injektion "Antworte auf Deutsch.", WP-A/ADR-0045-Nachzug).
_LANGUAGE_LEAKAGE_PHRASES = (
    "gleiche Sprache",
    "gleichen Sprache",
    "same language",
    "auf Deutsch",
    "in English",
)


def _collect_block_texts(node: object) -> list[str]:
    """Sammelt rekursiv alle `text`-Werte aus einem BlockNote-Body (Liste von
    Bloecken mit verschachteltem `content`/`children`)."""
    texts: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "text" and isinstance(value, str):
                texts.append(value)
            else:
                texts.extend(_collect_block_texts(value))
    elif isinstance(node, list):
        for item in node:
            texts.extend(_collect_block_texts(item))
    return texts


def test_no_rolled_out_template_body_contains_its_own_language_instruction() -> None:
    """Regressionsschutz (WP-A, ADR-0045-Nachzug): Sprachaussagen gehoeren
    AUSSCHLIESSLICH in die zentrale Renderer-Injektion
    (`services/agent_language.py::append_language_instruction`), NICHT in die
    Template-Bodies selbst — sonst entsteht wieder ein Widerspruch wie der
    ehemalige `ab-p8`/`cs-p6` ("...nutze die gleiche Sprache wie der
    Nutzer."/"...same language as the user.") neben der harten Injektion
    ("Antworte auf Deutsch."/"Respond in English."). Prueft ALLE sechs
    ausgerollten Template-Bodies in BEIDEN Packs (DE + EN, ueber
    `get_content_pack`)."""
    for pack in (_DE_PACK, _EN_PACK):
        for template in pack.templates:
            body = template.load_body(pack.locale)
            texts = _collect_block_texts(json.loads(body))
            for text in texts:
                for phrase in _LANGUAGE_LEAKAGE_PHRASES:
                    assert phrase not in text, (
                        f"Sprachaussage {phrase!r} in Template {template.slug!r} "
                        f"({pack.locale!r}): {text!r} — gehoert nur in "
                        "services/agent_language.py"
                    )

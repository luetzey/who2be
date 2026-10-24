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
import re
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
        "cases",
        "feedback_session",
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
    (kommasepariertes Item) darf in genau einem der Builder-Playbooks
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
        "builder_playbook_cases_body.json",
        "builder_playbook_feedback_session_body.json",
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
        "builder_playbook_cases_body.json",
        "builder_playbook_feedback_session_body.json",
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


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_conventions_tell_writers_to_read_source_format_before_writing(pack: ContentPack) -> None:
    """Schreiber-Regel (ADR-0058 §5.1 W58-2 B, §6.2) in DE und EN.

    Agenten schreiben Markdown; die Vorlage ist die Quellfassung
    `format="source"` mit `base_rev`, Teilaenderungen laufen ueber
    `edit_content`. Die Lesefassung `format="text"` ist keine Vorlage. Der
    Builder liest diese Resource vor jedem Bau, deshalb steht die Regel hier —
    als eigener Block, damit sie ueber ihren Anker zitierbar bleibt.
    """
    blocks = json.loads(pack.resource.load_body(pack.locale))
    rule = next((b for b in blocks if b["id"] == "res-conv-li-status-put-vollstand"), None)
    assert rule is not None, f"Regelblock fehlt in {pack.locale!r}"
    text = " ".join(_collect_block_texts(rule))
    assert "update_*" in text
    assert "edit_content" in text
    assert "base_rev" in text
    assert 'format="source"' in text
    assert 'format="text"' in text


_JSON_WRITE_PATH_PHRASES = (
    "BlockNote-JSON",
    "BlockNote JSON",
    "BlockNote-Dokument",
    "BlockNote document",
    "BlockNote-Block-Arrays",
    "BlockNote block arrays",
    "BlockNote-Profil",
    "BlockNote profile",
    "content-Array",
    "content array",
)


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_builder_content_describes_no_json_write_path(pack: ContentPack) -> None:
    """Nach dem harten Schnitt (ADR-0058 §7, W58-3 A) beschreibt kein verwalteter
    Builder-Inhalt mehr Editor-JSON als Schreibweg, und keiner verweist fuer das
    Schreiben auf `format="full"` als Vorlage."""
    filenames = [
        "builder_playbook_persona_body.json",
        "builder_playbook_playbook_body.json",
        "builder_playbook_agent_body.json",
        "builder_playbook_external_tool_body.json",
        "builder_playbook_feedback_session_body.json",
        "builder_resource_conventions_body.json",
    ]
    for filename in filenames:
        blocks = json.loads(load_sidecar(filename, pack.locale))
        for block in blocks:
            text = " ".join(_collect_block_texts(block))
            for phrase in _JSON_WRITE_PATH_PHRASES:
                assert phrase not in text, f"{pack.locale}/{filename}#{block['id']}: {phrase!r}"
            if "update_*" in text and 'format="full"' in text:
                assert 'format="source"' in text, f"{pack.locale}/{filename}#{block['id']}"


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_agent_playbook_markdown_example_converts_to_pills(pack: ContentPack) -> None:
    """Das Template-Beispiel im Agent-Playbook ist gueltiges Markdown des
    Schreibwegs (ADR-0058 §3.2): der Konverter, den die API beim Schreiben
    nutzt, macht aus den Tokens echte Placeholder-Pills."""
    from who2be_models.blocknote_markdown import from_markdown

    blocks = json.loads(load_sidecar("builder_playbook_agent_body.json", pack.locale))
    example = next(b for b in blocks if b["id"] == "pb-agent-code-placeholder")
    assert example["props"]["language"] == "markdown"
    converted = from_markdown(example["content"][0]["text"])
    pills = [
        (item["props"]["kind"], item["props"]["target_id"])
        for block in converted
        for item in block.get("content") or []
        if isinstance(item, dict) and item.get("type") == "placeholder"
    ]
    assert pills == [("persona-field", "name"), ("memory", "")]
    assert converted[0]["type"] == "heading"


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


# Builder schlank B2 (Content-Stand 21): Budget aus den Agent-Bau-Konventionen
# („Laengen & Wohin“): Profil <= 600 Woerter (Warnschwelle), Modus <= 250.
_PROFILE_WORD_LIMIT = 600
_MODE_WORD_LIMIT = 250


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_builder_persona_stays_within_length_budget(pack: ContentPack) -> None:
    """Profil und Modi der Builder-Persona halten die eigenen Richtwerte ein;
    der Builder soll vorleben, was er beim Bauen prueft."""
    profile = json.loads(pack.persona.load_content(pack.locale))
    words = len(" ".join(_collect_block_texts(profile)).split())
    assert words <= _PROFILE_WORD_LIMIT, words
    for mode in json.loads(pack.persona.load_modes(pack.locale)):
        mode_words = len(" ".join(_collect_block_texts(mode)).split())
        assert mode_words <= _MODE_WORD_LIMIT, (mode["name"], mode_words)


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_builder_persona_profile_has_no_duplicate_modes_or_tool_lists(pack: ContentPack) -> None:
    """B2: der Modi-Absatz steht nicht mehr im Profil (get_persona liefert die
    Modi selbst), und „Erlaubt“ zaehlt keine Werkzeuge auf (tools/list)."""
    profile = json.loads(pack.persona.load_content(pack.locale))
    ids = [block["id"] for block in profile]
    assert "bp-h-modes" not in ids
    assert "bp-li-allowed-fb" in ids, "Feedback-Regel (Migration 0055) muss bleiben"
    text = " ".join(_collect_block_texts(profile))
    tools = ("create_persona", "set_playbook_composes", "transition_persona", "restore_playbook")
    for tool in tools:
        assert tool not in text, tool


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_builder_template_loads_persona_at_runtime_without_tools_block(pack: ContentPack) -> None:
    """B2 (W5 a): das Builder-Template laedt die Persona per `persona-ref` und
    traegt keinen `tools-overview`-Block mehr; Lite bleibt unveraendert."""
    template = next(t for t in pack.templates if t.slug == "agent-builder")
    blocks = json.loads(template.load_body(pack.locale))
    pills = [
        (item["props"]["kind"], item["props"]["target_id"])
        for block in blocks
        for item in block.get("content") or []
        if isinstance(item, dict) and item.get("type") == "placeholder"
    ]
    assert ("persona-ref", "") in pills
    assert ("persona-field", "profile") not in pills
    assert all(kind != "tools-overview" for kind, _ in pills)


# Builder schlank B3 (Content-Stand 22): je Playbook die Konventions-Abschnitte,
# die es laedt (K4). Die Liste ist die Erwartung; der Test liest die Anker aus
# dem Playbook-Text und prueft sie gegen die Resource.
_CONVENTION_ANCHORS = {
    "persona": [
        "res-conv-h-modi",
        "res-conv-h-laengen",
        "res-conv-h-trigger",
        "res-conv-h-sprache",
    ],
    "playbook": ["res-conv-h-trigger", "res-conv-h-naming", "res-conv-h-laengen-budgets"],
    "agent": ["res-conv-h-policy", "res-conv-h-memory", "res-conv-h-managed"],
    "consistency": [
        "res-conv-h-trigger",
        "res-conv-h-modi",
        "res-conv-h-policy",
        "res-conv-h-laengen-budgets",
    ],
    "maintenance": ["res-conv-h-status", "res-conv-h-managed", "res-conv-h-graph"],
    "external_tool": ["res-conv-h-exttool", "res-conv-h-status"],
    "cases": ["res-conv-h-status", "res-conv-h-managed"],
    "feedback_session": ["res-conv-h-status", "res-conv-h-managed"],
}
_ANCHOR_PATTERN = re.compile(r"res-conv-[a-z0-9-]+")
_FETCH_CALL_PATTERN = re.compile(r"fetch_resource\(resource_id, block_ids=\[[^\]]*\]\)")


def _playbook_blocks(pack: ContentPack, key: str) -> list[dict[str, object]]:
    playbook = next(p for p in pack.playbooks if p.key == key)
    blocks: list[dict[str, object]] = json.loads(playbook.load_body(pack.locale))
    return blocks


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_playbook_convention_anchors_exist_as_resource_headings(pack: ContentPack) -> None:
    """K4: jedes Builder-Playbook laedt nur seine Konventions-Abschnitte, mit
    genau einem `fetch_resource(..., block_ids=[...])`-Aufruf. Jeder genannte
    Anker ist eine Ueberschrift der Resource (die Abschnittsregel schneidet nur
    Ueberschriften-Anker auf den ganzen Abschnitt). Rot, sobald ein Anker in der
    Resource umbenannt wird oder ein Playbook einen Anker verliert."""
    resource = json.loads(pack.resource.load_body(pack.locale))
    headings = {b["id"] for b in resource if b["type"] == "heading"}
    for key, expected in _CONVENTION_ANCHORS.items():
        text = " ".join(_collect_block_texts(_playbook_blocks(pack, key)))
        calls = _FETCH_CALL_PATTERN.findall(text)
        assert len(calls) == 1, (key, calls)
        assert _ANCHOR_PATTERN.findall(calls[0]) == expected, (key, calls[0])
        # Auch jeder andere Verweis im Playbook-Text zeigt auf eine Ueberschrift.
        missing = [a for a in _ANCHOR_PATTERN.findall(text) if a not in headings]
        assert not missing, (pack.locale, key, missing)


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_playbooks_drop_feedback_paragraph_and_full_conventions_load(pack: ContentPack) -> None:
    """K1 + K4: kein Builder-Playbook traegt mehr den Feedback-Absatz oder die
    Anweisung, die Konventionen ganz zu laden."""
    gone_ids = {
        "pb-feedback-h",
        "pb-feedback-p",
        "pb-maint-h-feedback",
        "pb-exttool-h-feedback",
        "d7-p81",
        "fg-p54",
    }
    for playbook in pack.playbooks:
        blocks = _playbook_blocks(pack, playbook.key)
        assert not gone_ids & {b["id"] for b in blocks}, playbook.key
        text = " ".join(_collect_block_texts(blocks))
        assert "NICHT automatisch mit" not in text, playbook.key
        assert "does NOT come along" not in text, playbook.key


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_agent_playbook_keeps_tools_overview_out_of_templates(pack: ContentPack) -> None:
    """PM 2026-10-22 (1): tools-overview gehoert standardmaessig nicht ins
    Template; die alte Lehre „gehoert in praktisch jedes Template“ ist weg."""
    blocks = _playbook_blocks(pack, "agent")
    rule = next(b for b in blocks if b["id"] == "pb-agent-li-placeholder-tools")
    text = " ".join(_collect_block_texts(rule))
    assert ("NICHT ins Template" in text) or ("does NOT belong in the template" in text)
    whole = " ".join(_collect_block_texts(blocks))
    assert "praktisch jedes Template" not in whole
    assert "practically every template" not in whole


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_playbook_playbook_no_longer_prescribes_purpose_and_tools_sections(
    pack: ContentPack,
) -> None:
    """PM 2026-10-22 (2): die Bauanleitung gibt „Zweck“ und „Tools &
    Operations“ nicht mehr als Pflichtgliederung vor, nur noch „Fallen“."""
    blocks = _playbook_blocks(pack, "playbook")
    atomic = next(b for b in blocks if b["id"] == "pb-playbook-create-p2-atomic")
    text = " ".join(_collect_block_texts(atomic))
    assert "Tools & Operations" not in text
    assert ("Fallen" in text) or ("Pitfalls" in text)


# Builder schlank B6 (Content-Stand 23, PM 2026-10-24 Option b): Teilabruf
# statt Teilen. Die Tests schneiden mit derselben Funktion, die der Server fuer
# `fetch_playbook(block_ids=...)` nutzt.
_WEG_IDS = ("d7-h-weg-a", "d7-h-weg-b", "d7-h-weg-c")
_BLOCK_IDS_PATTERN = re.compile(r"block_ids=\[([^\]]*)\]")


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_cases_signpost_loads_one_path_with_frame(pack: ContentPack) -> None:
    """Der Wegweiser der Fall-Triage nennt Rahmen + einen Weg. Je Weg schneidet
    `slice_playbook_body` genau diesen Weg heraus (Weg B zusaetzlich A5, auf den
    B4 verweist), Rahmen und Anti-Patterns bleiben, und der Teilabruf ist
    deutlich kleiner als der ganze Body."""
    from who2be_api.services.playbook_service import slice_playbook_body
    from who2be_models.blocknote_text import blocks_plain_text

    blocks = _playbook_blocks(pack, "cases")
    headings = {b["id"] for b in blocks if b["type"] == "heading"}
    sign = next(b for b in blocks if b["id"] == "d7-p-wegweiser")
    anchors = re.findall(
        r'"([^"]+)"', _BLOCK_IDS_PATTERN.findall(" ".join(_collect_block_texts(sign)))[0]
    )
    frame = [a for a in anchors if not a.startswith("<")]
    assert set(frame) <= headings, set(frame) - headings
    assert "d7-h-anti" in frame and "d7-h-grenzen" in frame and "d7-h-datenschutz" in frame
    full = len(blocks_plain_text(blocks).encode())
    for weg in _WEG_IDS:
        extra = ["d7-h-a5"] if weg == "d7-h-weg-b" else []
        sliced = json.loads(slice_playbook_body(json.dumps(blocks), [*frame, weg, *extra]))
        ids = {b["id"] for b in sliced}
        assert weg in ids
        assert not ids & (set(_WEG_IDS) - {weg}), weg
        assert {b["id"] for b in blocks if str(b["id"]).startswith("d7-b7")} <= ids
        size = len(blocks_plain_text(sliced).encode())
        assert size <= 0.7 * full, (weg, size, full)


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_builder_profile_carries_outline_rule_at_warn_threshold(pack: ContentPack) -> None:
    """Die Lade-Regel steht im immer geladenen Profil (nicht im Body, den sie
    erst steuern soll). Die Schwelle selbst nennt sie nicht: Budgetzahlen
    stehen nur in den Konventionen (test_budget_numbers_live_only_in_the_
    conventions), den Ueberschreitungs-Hinweis liefert der Server."""
    profile = json.loads(pack.persona.load_content(pack.locale))
    rule = " ".join(_collect_block_texts(next(b for b in profile if b["id"] == "bp-p-output-load")))
    assert 'format="outline"' in rule and "block_ids" in rule
    assert ("Warnschwelle" in rule) or ("warning threshold" in rule)
    assert ("nicht erneut holen" in rule) or ("again" in rule)


@pytest.mark.parametrize("pack", [_DE_PACK, _EN_PACK], ids=lambda p: p.locale)
def test_agent_policy_section_keeps_only_field_meaning(pack: ContentPack) -> None:
    """tool_policy ist gegen die Konventionen entdoppelt: Muster, Empfehlung und
    Eskalationsgrenzen stehen nur noch in res-conv-h-policy/-memory, die das
    Agent-Playbook ohnehin laedt; was nur im Playbook stand, steht jetzt dort."""
    from who2be_models.blocknote_text import section_blocks

    blocks = _playbook_blocks(pack, "agent")
    ids = {b["id"] for b in section_blocks(blocks, "pb-agent-h-policy")}
    for gone in ("pb-agent-li-policy-escalation", "pb-agent-li-policy-memory-empfehlung"):
        assert gone not in ids
    assert "pb-agent-li-policy-memory-grenze" not in ids
    resource = json.loads(pack.resource.load_body(pack.locale))
    conv = " ".join(
        _collect_block_texts(
            section_blocks(resource, "res-conv-h-policy")
            + section_blocks(resource, "res-conv-h-memory")
        )
    )
    for fact in ("admin", "read_only", "403", "is_within"):
        assert fact in conv, fact
    assert ("Repo-/Code-Fakten" in conv) or ("repo/code facts" in conv)

"""Drift-Guard fuer das tools/list-Payload-Budget (WP10, ADR-0047) und das
Antwort-Budget der teuersten Lese-Werkzeuge (docs/mcp-payload-budget.md).

Zwei verschiedene Budgets, beide hier, weil beide dasselbe Versagen haben:
die Laufzeit des Konsumenten legt eine zu grosse Payload weg, ohne einen
Fehler zu melden.

**tools/list (Kataloggroesse):** Claude Chat budgetiert die Connector-Payload
hart — waechst die tools/list-Antwort unbemerkt, fliegt nicht EIN Tool raus,
sondern die GESAMTE Tool-Liste.

- **Gesamt-Budget:** Baseline bei Einfuehrung (2026-08-13, 71 Tools) war
  110.133 Bytes; das Budget ist Baseline x ~1,45 und hat die Phase-2-Tools
  (WP19, 71 -> 83) aufgenommen, laesst aber keinen Raum fuer schleichende
  Docstring-Inflation. Reisst der Guard, zuerst Beschreibungen kuerzen bzw.
  die Fold-Reihenfolge aus dem Plan ziehen (`list_category_rules` ->
  `set_convention`), NICHT das Budget anheben.
- **Docstring-Cap fuer neue Domain-Module:** Die `tools/`-Module (WP8+)
  halten je Tool <= 1100 Zeichen Beschreibung. Der Bestand in `server.py`
  ist grandfathered (laengste Beschreibung 2047 Zeichen, transition-Tools
  mit `TRANSITION_RULE_DOC`).

**Antwortgroesse je Werkzeug:** Die Laufzeit deckelt eine EINZELNE
Tool-Antwort bei 50.000 Zeichen. Darueber sieht das Modell die Antwort nicht —
sie wird weggelegt, und der Server erfaehrt nichts davon. Die Tests unten
messen die SERIALISIERTE Antwort (`model_dump_json`), nicht Feldnamen: sie
halten die Zusage „die Antwort kommt an\", nicht die Zusage „ein Feld heisst
so\". Jeder Test fuehrt seine eigene Rot-Probe mit, indem er zuerst belegt,
dass der `full`-Pfad die Schwelle mit demselben Fixture tatsaechlich reisst —
faellt der `text`-Pfad weg, werden beide Pfade gleich gross und der Test wird
rot.
"""

import ast
import asyncio
import importlib
import inspect
import json
import pathlib
import pkgutil
from collections.abc import Callable
from uuid import UUID, uuid4

import httpx
import pytest
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ValidationError

from who2be_mcp import server
from who2be_mcp import tools as tools_pkg
from who2be_mcp.client import AnyVersionRead, ApiClient
from who2be_mcp.server import (
    _RESPONSE_FORMATS,
    fetch_agent,
    get_persona,
    list_playbooks,
    list_versions,
    mcp,
)
from who2be_models.playbook import PlaybookContent
from who2be_models.resource import ResourceContent
from who2be_models.system_prompt_template import SystemPromptTemplateContent

# Baseline 2026-08-13: 71 Tools / 110_133 Bytes (utf-8, name+description+
# inputSchema). Budget ~x1,45 — trug den Ausbau auf 83 Tools (WP19 + die
# nachgezogenen `list_tables`/`delete_table`), mehr nicht.
_PAYLOAD_BUDGET_BYTES = 160_000
_NEW_TOOL_DOC_CAP = 1_100

# Die Schwelle der Konsumenten-Laufzeit fuer eine EINZELNE Tool-Antwort. Keine
# Who2Be-Einstellung, sondern eine Randbedingung — nicht anheben, wenn ein Test
# reisst; stattdessen die Antwort kleiner machen.
_RESPONSE_CHAR_LIMIT = 50_000

_WORKSPACE_ID = uuid4()


async def _tools_payload_bytes() -> int:
    tools = await mcp.list_tools(run_middleware=False)
    payload = [
        {"name": t.name, "description": t.description or "", "inputSchema": t.parameters}
        for t in tools
    ]
    return len(json.dumps(payload, ensure_ascii=False).encode())


def test_tools_list_payload_stays_under_budget() -> None:
    size = asyncio.run(_tools_payload_bytes())
    assert size <= _PAYLOAD_BUDGET_BYTES, (
        f"tools/list-Payload {size} Bytes > Budget {_PAYLOAD_BUDGET_BYTES} — "
        "Beschreibungen kuerzen oder Tools falten (Plan-Fold-Reihenfolge), "
        "nicht das Budget anheben."
    )


# Der Satz, den jede PUT-Beschreibung tragen muss (ADR-0056 Abschnitt 5,
# Schicht 2): wer die Lesefassung als Vorlage nimmt, leert beim PUT den Inhalt.
_PUT_FULL_HINT = 'Vorlage im Vollstand lesen (`format="full"`'


def _put_update_tools() -> dict[str, str]:
    """`update_*`-Werkzeuge mit PUT-Semantik, abgeleitet aus dem Schema.

    PUT heisst hier: `data` verlangt `content`, der neue Stand ersetzt den
    alten vollstaendig. Teil-Updates (`update_agent`, `update_node`: weggelassen
    = unveraendert) haben kein Pflicht-`content` und fallen heraus. Keine
    zweite Namensliste, die veraltet.
    """
    tools = asyncio.run(mcp.list_tools(run_middleware=False))
    found: dict[str, str] = {}
    for tool in tools:
        if not tool.name.startswith("update_"):
            continue
        params = tool.parameters or {}
        data = (params.get("properties") or {}).get("data")
        if not isinstance(data, dict):
            continue
        ref = data.get("$ref")
        schema = params.get("$defs", {}).get(ref.rsplit("/", 1)[-1], {}) if ref else data
        if "content" in (schema.get("required") or []):
            found[tool.name] = " ".join((tool.description or "").split())
    return found


def test_every_put_update_tool_tells_writers_to_read_full_format() -> None:
    """Jede PUT-Beschreibung nennt `format="full"` als Vorlage (ADR-0056 §5).

    Rot-Probe ist die Ableitung selbst: die Mindestmenge stellt sicher, dass
    der Guard die fuenf heutigen PUT-Werkzeuge wirklich findet und nicht
    still ueber eine leere Menge laeuft.
    """
    put_tools = _put_update_tools()
    assert {
        "update_persona",
        "update_playbook",
        "update_resource",
        "update_external_tool",
        "update_system_prompt",
    } <= set(put_tools), f"PUT-Ableitung findet zu wenig: {sorted(put_tools)}"

    missing = sorted(name for name, doc in put_tools.items() if _PUT_FULL_HINT not in doc)
    assert not missing, (
        f'Ohne Hinweis auf `format="full"`: {missing}. Ein PUT auf Basis der '
        "Lesefassung leert den Inhalt (ADR-0056 Abschnitt 5)."
    )


@pytest.mark.parametrize(
    "module_name",
    [name for _, name, _ in pkgutil.iter_modules(tools_pkg.__path__)],
)
def test_new_domain_tool_docstrings_stay_capped(module_name: str) -> None:
    """Jedes Tool der neuen `tools/`-Module haelt den 1100-Zeichen-Cap."""
    module = importlib.import_module(f"who2be_mcp.tools.{module_name}")
    offenders = {
        name: len(inspect.getdoc(fn) or "")
        for name, fn in vars(module).items()
        if inspect.iscoroutinefunction(fn)
        and not name.startswith("_")
        and len(inspect.getdoc(fn) or "") > _NEW_TOOL_DOC_CAP
    }
    assert not offenders, f"Docstrings ueber {_NEW_TOOL_DOC_CAP} Zeichen: {offenders}"


# ---------------------------------------------------------------------------
# Antwortgroesse je Werkzeug
# ---------------------------------------------------------------------------


def _factory(handler: Callable[[httpx.Request], httpx.Response]) -> Callable[[], object]:
    transport = httpx.MockTransport(handler)

    async def _build() -> ApiClient:
        return ApiClient("http://test", "token", _WORKSPACE_ID, transport=transport)

    return _build


def _chars(result: object) -> int:
    """Groesse der Antwort so, wie sie beim Agenten ankommt (serialisiert)."""
    if isinstance(result, list):
        return len(json.dumps([json.loads(item.model_dump_json()) for item in result]))
    assert isinstance(result, BaseModel)
    return len(result.model_dump_json())


def _assert_text_path_fits(full: object, text: object, tool: str) -> None:
    """Rot-Probe + Zusage in einem: `full` muss reissen, `text` muss passen.

    Die erste Assertion ist der Regressionsanker — ohne sie koennte ein zu
    kleines Fixture den Test gruen halten, ohne dass der Text-Pfad etwas
    beweist. Entfaellt der Text-Pfad, liefern beide Aufrufe dieselbe Groesse
    und die zweite Assertion faellt.
    """
    full_chars, text_chars = _chars(full), _chars(text)
    assert full_chars > _RESPONSE_CHAR_LIMIT, (
        f"{tool}: Fixture zu klein ({full_chars} Zeichen) — der full-Pfad muss "
        "die Schwelle reissen, sonst beweist der text-Pfad nichts."
    )
    assert text_chars <= _RESPONSE_CHAR_LIMIT, (
        f"{tool}: text-Pfad {text_chars} Zeichen > Obergrenze {_RESPONSE_CHAR_LIMIT}."
    )


def _playbook_content(version: AnyVersionRead) -> PlaybookContent:
    """Verengt den Union-Typ auf den Playbook-Fall — mit Pruefung, nicht per Annahme."""
    content = version.content
    assert isinstance(content, PlaybookContent)
    return content


def _resource_content(version: AnyVersionRead) -> ResourceContent:
    """Verengt den Union-Typ auf den Resource-Fall."""
    content = version.content
    assert isinstance(content, ResourceContent)
    return content


def _fat_blocks(count: int) -> list[dict[str, object]]:
    """BlockNote-Bloecke mit realistischem Struktur-Overhead.

    Ein Editor-Block traegt pro Absatz ~250 Zeichen Struktur (props, styles,
    children) auf ~60 Zeichen Nutztext — genau das Verhaeltnis, das die
    Payload aufblaeht.
    """
    return [
        {
            "id": f"b{index}",
            "type": "paragraph",
            "props": {
                "backgroundColor": "default",
                "textColor": "default",
                "textAlignment": "left",
            },
            "content": [
                {
                    "type": "text",
                    "text": f"Abschnitt {index}: Profiltext dieses Absatzes.",
                    "styles": {},
                }
            ],
            "children": [],
        }
        for index in range(count)
    ]


def _fat_blocknote_body(paragraphs: int) -> str:
    """Derselbe Ballast als stringifiziertes JSON (so liefert die API `body`)."""
    return json.dumps(_fat_blocks(paragraphs), ensure_ascii=False)


def _persona_payload(persona_id: UUID, blocks: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": str(persona_id),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": "Coder",
        "current_version": 1,
        "current_status": "active",
        "has_pending_draft": False,
        "content": {
            "description": "Autonomer Code-Agent",
            "system_prompt": "",
            "traits": [],
            "tags": ["code-agent"],
            "content": {"description": "", "blocks": blocks},
            "modes": [
                {
                    "name": "Refiner",
                    "trigger": "issue veredeln",
                    "is_default": False,
                    "identity_add": "Veredelungs-Haltung",
                    "output_style_override": "",
                }
            ],
        },
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _playbook_payload(name: str, body: str) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": name,
        "current_version": 1,
        "current_status": "active",
        "has_pending_draft": False,
        "type": "workflow",
        "tags": ["workflow"],
        "triggers": "arbeite Task [X] ab",
        "content": {"description": f"Beschreibung von {name}", "body": body, "type": "workflow"},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _text_format_tools() -> set[str]:
    """Registrierte Tools, deren `format` der Budget-Zuschnitt ist (`full`/`text`).

    Gezielt ueber den Wertebereich, nicht ueber den Parameternamen: `query_table`
    hat auch ein `format`, meint damit aber das Ausgabeformat (`json`/`markdown`/
    `csv`) und deckelt seine Antwort ueber `limit`. Ein Guard, der nur auf den
    Namen schaut, zieht diesen Fall zu Unrecht herein.
    """
    tools = asyncio.run(mcp.list_tools(run_middleware=False))
    found = set()
    for tool in tools:
        schema = ((tool.parameters or {}).get("properties") or {}).get("format")
        if not isinstance(schema, dict):
            continue
        if set(schema.get("enum") or []) == _RESPONSE_FORMATS or schema.get("default") == "full":
            found.add(tool.name)
    return found


def _budget_test_names() -> set[str]:
    """Alle Testfunktionsnamen des MCP-Testverzeichnisses (per AST, nicht per Import).

    Ueber das ganze Verzeichnis, weil die Tests da liegen, wo ihr Werkzeug
    getestet wird: `fetch_playbook` etwa in `test_resource_tools.py`. Ein Guard,
    der nur die eigene Datei kennt, meldet einen gedeckten Fall als Luecke.
    """
    names: set[str] = set()
    for path in pathlib.Path(__file__).parent.glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names |= {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        }
    return names


def test_every_format_aware_tool_has_a_budget_test() -> None:
    """Ein neues `format`-Werkzeug ohne Budget-Nachweis faellt hier auf.

    Der Zuschnitt ist nur so gut wie sein Beleg: ein Werkzeug, das `format`
    anbietet, aber keinen Test mit eigener Rot-Probe hat, sieht geschuetzt aus
    und ist es nicht. Der Guard liest die tatsaechlichen Tool-Schemata und die
    tatsaechlichen Testnamen — keine zweite Liste, die veraltet.

    Reisst er, ist die Antwort: einen Test nach dem Muster der bestehenden
    schreiben (Fixture, dessen `full`-Pfad die Grenze reisst, dann die Zusage
    fuer `text`) — nicht den Namen hier eintragen.
    """
    format_aware = _text_format_tools()
    assert format_aware, "Kein Werkzeug mit Budget-`format` gefunden — der Guard misst nichts."

    test_names = _budget_test_names()
    missing = {
        tool
        for tool in format_aware
        if not any(tool in name and "format" in name for name in test_names)
    }
    assert not missing, (
        f"Werkzeuge mit `format`, aber ohne Budget-Test: {sorted(missing)}. "
        "Jeder Zuschnitt braucht seinen eigenen Nachweis (Rot-Probe), sonst ist er "
        "nur behauptet — siehe docs/mcp-payload-budget.md, Abschnitt Regressionsschutz."
    )


def test_system_prompt_body_cannot_be_emptied_for_a_cheap_response() -> None:
    """Belegt, WARUM `list_system_prompts`/`get_system_prompt` keinen `format` haben.

    Das Schema verlangt einen nicht-leeren Body (`min_length=1`) — der Zuschnitt
    „Body leeren\" wuerde hier eine schema-ungueltige Antwort erzeugen, also
    einen Validierungsfehler statt einer kleineren Antwort. Der Fall braucht ein
    eigenes Summary-Modell (`docs/mcp-payload-budget.md`, Abschnitt „Offen\").

    Wird das Limit irgendwann gelockert, faellt dieser Test — und genau dann ist
    der billige Zuschnitt moeglich und soll nachgezogen werden.
    """
    with pytest.raises(ValidationError):
        SystemPromptTemplateContent(description="Template", body="")

    # Gegenprobe: derselbe Aufruf mit Inhalt gelingt — der Fehler oben kommt von
    # `min_length`, nicht von einem anderen Feld.
    assert SystemPromptTemplateContent(description="Template", body="x").body == "x"

    # Und: ein Body am erlaubten Maximum sprengt das Antwortbudget allein, ohne
    # jeden Rahmen — deshalb ist `get_system_prompt` ein struktureller Fall.
    field = SystemPromptTemplateContent.model_fields["body"]
    max_length = next(
        m.max_length for m in field.metadata if getattr(m, "max_length", None) is not None
    )
    assert max_length >= _RESPONSE_CHAR_LIMIT, (
        f"`body` ist auf {max_length} Zeichen begrenzt und liegt damit unter dem "
        f"Antwortbudget {_RESPONSE_CHAR_LIMIT} — `get_system_prompt` ist dann kein "
        "struktureller Fall mehr; docs/mcp-payload-budget.md nachziehen."
    )


def test_get_persona_text_format_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Das Persona-Profil kommt an, ohne das Editor-JSON doppelt zu bezahlen."""
    persona_id = uuid4()
    payload = _persona_payload(persona_id, _fat_blocks(190))
    rendered = "\n\n".join(f"Abschnitt {i}: Profiltext dieses Absatzes." for i in range(190))

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/personas/{persona_id}/rendered"):
            return httpx.Response(200, json={"body_rendered": rendered, "unresolved": []})
        if path.endswith(f"/personas/{persona_id}/playbooks"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/personas/{persona_id}"):
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"detail": "weg"})

    monkeypatch.setattr(server, "build_client", _factory(handler))

    full = asyncio.run(get_persona(str(persona_id)))
    text = asyncio.run(get_persona(str(persona_id), format="text"))

    _assert_text_path_fits(full, text, "get_persona")
    # Gekuerzt wird die Editor-Struktur, nicht der Inhalt: das Profil kommt
    # vollstaendig an, und die Modi (die Logik des Agenten) bleiben erhalten.
    assert "Abschnitt 189" in text.body_rendered
    assert text.persona.content.modes[0].trigger == "issue veredeln"
    assert text.persona.content.description == full.persona.content.description


def test_get_persona_default_format_keeps_editor_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Additiv: ohne `format` bleibt die Antwort unveraendert vollstaendig."""
    persona_id = uuid4()
    blocks = _fat_blocks(4)
    payload = _persona_payload(persona_id, blocks)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/personas/{persona_id}/rendered"):
            return httpx.Response(200, json={"body_rendered": "Profil", "unresolved": []})
        if path.endswith(f"/personas/{persona_id}/playbooks"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/personas/{persona_id}"):
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"detail": "weg"})

    monkeypatch.setattr(server, "build_client", _factory(handler))

    default = asyncio.run(get_persona(str(persona_id)))
    explicit = asyncio.run(get_persona(str(persona_id), format="full"))
    text = asyncio.run(get_persona(str(persona_id), format="text"))

    assert default.persona.content.content is not None
    assert len(default.persona.content.content.blocks) == len(blocks)
    assert explicit.persona.content.content is not None
    assert len(explicit.persona.content.content.blocks) == len(blocks)
    assert text.persona.content.content is not None
    assert text.persona.content.content.blocks == []


def test_get_persona_rejects_unknown_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Tippfehler im `format` faellt auf, statt still den Default zu liefern.

    Das Fixture antwortet ABSICHTLICH erfolgreich: ohne die Format-Pruefung
    wuerde der Aufruf durchlaufen und stillschweigend `full` liefern. Nur so
    belegt der Test die Pruefung und nicht bloss irgendeinen Fehler.
    """
    persona_id = uuid4()
    payload = _persona_payload(persona_id, _fat_blocks(2))

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/personas/{persona_id}/rendered"):
            return httpx.Response(200, json={"body_rendered": "Profil", "unresolved": []})
        if path.endswith(f"/personas/{persona_id}/playbooks"):
            return httpx.Response(200, json=[])
        if path.endswith(f"/personas/{persona_id}"):
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"detail": "weg"})

    monkeypatch.setattr(server, "build_client", _factory(handler))

    # Gegenprobe: derselbe Aufruf mit gueltigem Zuschnitt gelingt — der Fehler
    # unten kommt also von `format`, nicht von der gemockten API.
    assert asyncio.run(get_persona(str(persona_id))).persona.name == "Coder"
    with pytest.raises(ToolError, match="Ungueltiges format"):
        asyncio.run(get_persona(str(persona_id), format="plain"))


def test_get_persona_text_format_empties_linked_playbook_bodies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Regelfall: eine Persona MIT verknuepften Playbooks.

    `get_persona` liefert `PersonaWithPlaybooks` — die Playbook-Bodies liegen in
    derselben Antwort wie das Profil. Das Fixture ist absichtlich so gebaut,
    dass die Persona selbst klein ist und der `full`-Pfad die Grenze **allein
    ueber die Playbooks** reisst: greift der Zuschnitt nur am Profil, bleibt der
    text-Pfad ueber der Grenze und dieser Test faellt. Eine Persona ohne
    verknuepfte Playbooks ist beim Boot-Schritt der Ausnahmefall, nicht der
    Regelfall.
    """
    persona_id = uuid4()
    payload = _persona_payload(persona_id, _fat_blocks(20))
    body = _fat_blocknote_body(60)
    linked = [_playbook_payload(f"Playbook {index}", body) for index in range(5)]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith(f"/personas/{persona_id}/rendered"):
            return httpx.Response(200, json={"body_rendered": "Profil", "unresolved": []})
        if path.endswith(f"/personas/{persona_id}/playbooks"):
            return httpx.Response(200, json=linked)
        if path.endswith(f"/personas/{persona_id}"):
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"detail": "weg"})

    monkeypatch.setattr(server, "build_client", _factory(handler))

    full = asyncio.run(get_persona(str(persona_id)))
    text = asyncio.run(get_persona(str(persona_id), format="text"))

    # Gegenprobe zur Abgrenzung: die Persona-Bloecke allein tragen die Antwort
    # NICHT ueber die Grenze — was sie reisst, sind die Playbook-Bodies.
    persona_only = len(full.persona.model_dump_json())
    assert persona_only <= _RESPONSE_CHAR_LIMIT, (
        f"Fixture verfehlt seinen Zweck: die Persona allein ist mit {persona_only} "
        "Zeichen schon zu gross — dann belegt der Test nicht den Playbook-Zuschnitt."
    )

    _assert_text_path_fits(full, text, "get_persona(mit Playbooks)")
    # Der Katalog bleibt brauchbar: was die Auswahl traegt, ist vollstaendig da.
    assert len(text.playbooks) == len(full.playbooks) == 5
    assert [p.name for p in text.playbooks] == [p.name for p in full.playbooks]
    assert all(p.triggers == "arbeite Task [X] ab" for p in text.playbooks)
    assert all(p.content.description.startswith("Beschreibung von") for p in text.playbooks)
    assert all(p.content.body == "" for p in text.playbooks)
    assert all(p.content.body == body for p in full.playbooks)


def test_fetch_agent_text_format_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der gerenderte Prompt traegt das Profil — die Bloecke sind Dublette."""
    agent_id = uuid4()
    persona = _persona_payload(uuid4(), _fat_blocks(230))
    payload = {
        "id": str(agent_id),
        "name": "Coder",
        "persona": persona,
        "system_prompt_rendered": "Du bist Coder.\n\nAntworte auf Deutsch.",
        "system_prompt_template_id": str(uuid4()),
        "locale": "de",
    }

    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=payload))
    )

    full = asyncio.run(fetch_agent(str(agent_id)))
    text = asyncio.run(fetch_agent(str(agent_id), format="text"))

    _assert_text_path_fits(full, text, "fetch_agent")
    # Der Prompt — der eigentliche Zweck des Tools — bleibt unberuehrt.
    assert text.system_prompt_rendered == full.system_prompt_rendered
    assert text.persona.name == full.persona.name


def test_list_playbooks_text_format_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Katalog beantwortet die Auswahl, nicht den Inhalt jedes Eintrags."""
    body = _fat_blocknote_body(60)
    payload = [_playbook_payload(f"Playbook {index}", body) for index in range(8)]

    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=payload))
    )

    full = asyncio.run(list_playbooks())
    text = asyncio.run(list_playbooks(format="text"))

    _assert_text_path_fits(full, text, "list_playbooks")
    # Was die Auswahl traegt, bleibt vollstaendig: Name, Beschreibung, Tags,
    # Triggers — nur das Editor-JSON faellt weg.
    assert len(text) == len(full) == 8
    assert [p.name for p in text] == [p.name for p in full]
    assert all(p.triggers == "arbeite Task [X] ab" for p in text)
    assert all(p.content.description.startswith("Beschreibung von") for p in text)
    assert all(p.content.body == "" for p in text)
    assert all(p.content.body == body for p in full)


def test_list_versions_text_format_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Historie beantwortet „welche Versionen\", nicht „welcher Inhalt\"."""
    entity_id = uuid4()
    body = _fat_blocknote_body(60)
    payload = [
        {
            "id": str(uuid4()),
            "version": version,
            "status": "active" if version == 8 else "inactive",
            "locale": "de",
            "content": {"description": f"Stand {version}", "body": body, "type": "workflow"},
            "created_by": str(uuid4()),
            "created_at": "2026-01-01T00:00:00Z",
        }
        for version in range(1, 9)
    ]

    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=payload))
    )

    full = asyncio.run(list_versions("playbook", str(entity_id)))
    text = asyncio.run(list_versions("playbook", str(entity_id), format="text"))

    _assert_text_path_fits(full, text, "list_versions")
    # Die Metadaten sind der Zweck der Liste und bleiben vollstaendig.
    assert [v.version for v in text] == [v.version for v in full]
    assert [v.status for v in text] == [v.status for v in full]
    assert [v.created_at for v in text] == [v.created_at for v in full]
    assert all(_playbook_content(v).description.startswith("Stand") for v in text)
    assert all(_playbook_content(v).body == "" for v in text)


def test_list_versions_text_format_empties_resource_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Zuschnitt greift typ-agnostisch: Resources tragen `blocks`, nicht `body`.

    Ohne diesen Test koennte der Zuschnitt nur den Playbook-Fall treffen und
    fuer Resources still nichts tun — der Fall, den eine reine
    Feldnamen-Pruefung nicht faengt.
    """
    entity_id = uuid4()
    blocks = _fat_blocks(60)
    payload = [
        {
            "id": str(uuid4()),
            "version": version,
            "status": "inactive",
            "locale": "de",
            "content": {"description": f"Stand {version}", "blocks": blocks, "tags": ["doku"]},
            "created_by": str(uuid4()),
            "created_at": "2026-01-01T00:00:00Z",
        }
        for version in range(1, 9)
    ]

    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=payload))
    )

    full = asyncio.run(list_versions("resource", str(entity_id)))
    text = asyncio.run(list_versions("resource", str(entity_id), format="text"))

    _assert_text_path_fits(full, text, "list_versions(resource)")
    assert all(_resource_content(v).blocks == [] for v in text)
    assert all(_resource_content(v).tags == ["doku"] for v in text)
    assert all(len(_resource_content(v).blocks) == len(blocks) for v in full)

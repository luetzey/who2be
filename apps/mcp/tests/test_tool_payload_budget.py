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
from fastmcp import Client
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ValidationError

from who2be_mcp import server
from who2be_mcp import tools as tools_pkg
from who2be_mcp.client import ApiClient
from who2be_mcp.server import (
    _RESPONSE_FORMATS,
    PersonaWithPlaybooks,
    diff_versions,
    fetch_agent,
    fetch_resource,
    get_external_tool,
    get_persona,
    get_system_prompt,
    get_version,
    list_external_tools,
    list_playbooks,
    list_system_prompts,
    list_versions,
    mcp,
)
from who2be_models import AgentWithRenderedPrompt
from who2be_models.external_tool import ExternalToolContent
from who2be_models.system_prompt_template import SystemPromptTemplateContent

# Baseline 2026-08-13: 71 Tools / 110_133 Bytes (utf-8, name+description+
# inputSchema). Budget ~x1,45 — trug den Ausbau auf 83 Tools (WP19 + die
# nachgezogenen `list_tables`/`delete_table`), mehr nicht. Seit 2026-10-06
# misst der Test die Draht-Form (inkl. `title`/`_meta` aus fastmcp 4):
# 86 Tools / 142_295 Bytes.
_PAYLOAD_BUDGET_BYTES = 160_000
_NEW_TOOL_DOC_CAP = 1_100

# Die Schwelle der Konsumenten-Laufzeit fuer eine EINZELNE Tool-Antwort. Keine
# Who2Be-Einstellung, sondern eine Randbedingung — nicht anheben, wenn ein Test
# reisst; stattdessen die Antwort kleiner machen.
_RESPONSE_CHAR_LIMIT = 50_000

_WORKSPACE_ID = uuid4()


async def _tools_payload_bytes() -> int:
    """Groesse der `tools`-Liste so, wie `tools/list` sie auf den Draht legt.

    Gemessen wird ueber einen In-Memory-Client, also durch den echten
    `tools/list`-Handler samt Middleware — nicht ueber eine selbst gebaute
    Teilmenge der Felder. Seit fastmcp 4 traegt jedes Tool zusaetzlich `title`
    und `_meta`; eine Messung nur ueber name/description/inputSchema sah diese
    Felder nicht (rund 2,4 KB bei 86 Tools). Gezaehlt wird die `tools`-Liste
    (utf-8, `ensure_ascii=False`), ohne den JSON-RPC-Umschlag.
    """
    async with Client(mcp) as client:
        result = await client.list_tools_mcp()
    tools = result.model_dump(mode="json", by_alias=True, exclude_none=True)["tools"]
    return len(json.dumps(tools, ensure_ascii=False).encode())


def test_tools_list_payload_stays_under_budget() -> None:
    size = asyncio.run(_tools_payload_bytes())
    assert size <= _PAYLOAD_BUDGET_BYTES, (
        f"tools/list-Payload {size} Bytes > Budget {_PAYLOAD_BUDGET_BYTES} — "
        "Beschreibungen kuerzen oder Tools falten (Plan-Fold-Reihenfolge), "
        "nicht das Budget anheben."
    )


@pytest.mark.parametrize("field", ["title", "meta"])
def test_tools_list_payload_counts_wire_only_fields(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rot-Probe: `title` und `_meta` zaehlen mit, obwohl sie nicht im Schema stehen.

    Ein einzelnes Tool bekommt ein aufgeblaehtes Feld, das klar ueber das
    Budget traegt. Misst `_tools_payload_bytes` wieder nur name/description/
    inputSchema, bleibt die Groesse unveraendert und dieser Test faellt.
    """
    tool = asyncio.run(mcp.list_tools(run_middleware=False))[0]
    before = asyncio.run(_tools_payload_bytes())
    # Spielraum: ein gesetzter `title` ersetzt den abgeleiteten Default-Titel.
    pad = "X" * (_PAYLOAD_BUDGET_BYTES - before + 1_000)
    if field == "title":
        monkeypatch.setattr(tool, "title", (tool.title or "") + pad)
    else:
        monkeypatch.setattr(tool, "meta", {**(tool.meta or {}), "probe": pad})

    after = asyncio.run(_tools_payload_bytes())

    assert after > _PAYLOAD_BUDGET_BYTES, (
        f"Aufgeblaehtes `{field}` ({len(pad)} Zeichen) nicht gemessen: {before} -> {after} "
        "Bytes. Die Messung sieht die Draht-Form von tools/list nicht."
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
    """Groesse der Antwort so, wie sie beim Agenten ankommt (serialisiert).

    Der Markdown-Zuschnitt (ADR-0056, Option B) IST der Text, der ankommt.
    """
    if isinstance(result, str):
        return len(result)
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

    Erkannt wird ein Budget-Zuschnitt an seinem Default (`full` oder, seit
    ADR-0056, `text`) bzw. am Enum `{full, text}` — `query_table` hat weder das
    eine noch das andere.
    """
    tools = asyncio.run(mcp.list_tools(run_middleware=False))
    found = set()
    for tool in tools:
        schema = ((tool.parameters or {}).get("properties") or {}).get("format")
        if not isinstance(schema, dict):
            continue
        if set(schema.get("enum") or []) == _RESPONSE_FORMATS or schema.get("default") in (
            _RESPONSE_FORMATS
        ):
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
    # Rot-Probe der Erkennung: die umgestellten Werkzeuge (Default `text`) und
    # die noch nicht umgestellten (Default `full`) werden beide gefunden.
    assert {"get_persona", "fetch_agent", "list_playbooks", "fetch_playbook"} <= format_aware
    assert "list_versions" in format_aware
    assert "query_table" not in format_aware

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
    """Belegt, WARUM `get_system_prompt` den Body als Text traegt statt ihn zu leeren.

    Das Schema verlangt einen nicht-leeren Body (`min_length=1`) — der Zuschnitt
    „Body leeren\" wuerde hier eine schema-ungueltige Antwort erzeugen, also
    einen Validierungsfehler statt einer kleineren Antwort. Der Markdown-Zuschnitt
    (ADR-0056) umgeht das: er traegt den Body als Klartext ohne Editor-Struktur
    (`test_get_system_prompt_text_format_stays_under_response_limit`).

    Wird das Limit irgendwann gelockert, faellt dieser Test — dann ist der
    Docstring hier und `docs/mcp-payload-budget.md` nachzuziehen.
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

    full = asyncio.run(get_persona(str(persona_id), format="full"))
    text = asyncio.run(get_persona(str(persona_id), format="text"))

    _assert_text_path_fits(full, text, "get_persona")
    # Gekuerzt wird die Editor-Struktur, nicht der Inhalt: das Profil kommt
    # vollstaendig an, und die Modi (die Logik des Agenten) bleiben erhalten.
    assert isinstance(full, PersonaWithPlaybooks)
    assert isinstance(text, str)
    assert "Abschnitt 189" in text
    assert "**Trigger:** issue veredeln" in text
    assert full.persona.content.description in text
    assert '"props"' not in text


def test_get_persona_default_format_is_markdown_and_full_keeps_editor_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default ist Markdown (ADR-0056); `full` behaelt die Editor-Bloecke."""
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

    assert isinstance(explicit, PersonaWithPlaybooks)
    assert explicit.persona.content.content is not None
    assert len(explicit.persona.content.content.blocks) == len(blocks)
    # Rot-Probe: liefert der Default wieder das Modell, faellt der Typ.
    assert isinstance(default, str)
    assert default == text
    with pytest.raises(json.JSONDecodeError):
        json.loads(text)
    assert '"blocks"' not in text


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
    valid = asyncio.run(get_persona(str(persona_id), format="full"))
    assert isinstance(valid, PersonaWithPlaybooks)
    assert valid.persona.name == "Coder"
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

    full = asyncio.run(get_persona(str(persona_id), format="full"))
    text = asyncio.run(get_persona(str(persona_id), format="text"))

    # Gegenprobe zur Abgrenzung: die Persona-Bloecke allein tragen die Antwort
    # NICHT ueber die Grenze — was sie reisst, sind die Playbook-Bodies.
    assert isinstance(full, PersonaWithPlaybooks)
    persona_only = len(full.persona.model_dump_json())
    assert persona_only <= _RESPONSE_CHAR_LIMIT, (
        f"Fixture verfehlt seinen Zweck: die Persona allein ist mit {persona_only} "
        "Zeichen schon zu gross — dann belegt der Test nicht den Playbook-Zuschnitt."
    )

    _assert_text_path_fits(full, text, "get_persona(mit Playbooks)")
    # Der Katalog bleibt brauchbar: was die Auswahl traegt, ist vollstaendig da —
    # Name, id, Trigger je Playbook; der Body nicht (den holt `fetch_playbook`).
    assert isinstance(text, str)
    assert len(full.playbooks) == 5
    for playbook in full.playbooks:
        assert f"- {playbook.name} (`{playbook.id}`) — Trigger: arbeite Task [X] ab" in text
    assert all(p.content.body == body for p in full.playbooks)
    assert "Abschnitt 0: Profiltext" not in text


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

    full = asyncio.run(fetch_agent(str(agent_id), format="full"))
    text = asyncio.run(fetch_agent(str(agent_id), format="text"))

    _assert_text_path_fits(full, text, "fetch_agent")
    # Der Prompt — der eigentliche Zweck des Tools — bleibt unberuehrt.
    assert isinstance(full, AgentWithRenderedPrompt)
    assert isinstance(text, str)
    assert full.system_prompt_rendered in text
    assert f"- persona: {full.persona.name} ({full.persona.id})" in text


def test_list_playbooks_text_format_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Katalog beantwortet die Auswahl, nicht den Inhalt jedes Eintrags."""
    body = _fat_blocknote_body(60)
    payload = [_playbook_payload(f"Playbook {index}", body) for index in range(8)]

    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=payload))
    )

    full = asyncio.run(list_playbooks(format="full"))
    text = asyncio.run(list_playbooks(format="text"))

    _assert_text_path_fits(full, text, "list_playbooks")
    # Was die Auswahl traegt, bleibt vollstaendig: Name, id, Beschreibung,
    # Triggers — nur das Editor-JSON faellt weg.
    assert isinstance(full, list)
    assert isinstance(text, str)
    assert len(full) == 8
    assert text.startswith("# Playbooks (8)\n")
    for playbook in full:
        assert f"## {playbook.name}\n" in text
        assert f"- id: {playbook.id}" in text
        assert playbook.content.description in text
    assert text.count("- trigger: arbeite Task [X] ab") == 8
    assert all(p.content.body == body for p in full)
    assert '"props"' not in text


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

    full = asyncio.run(list_versions("playbook", str(entity_id), format="full"))
    text = asyncio.run(list_versions("playbook", str(entity_id), format="text"))

    _assert_text_path_fits(full, text, "list_versions")
    # Die Metadaten sind der Zweck der Liste und bleiben vollstaendig, je
    # Version ein Kopf; der Inhalt (den `get_version` liefert) faellt weg.
    assert isinstance(full, list)
    assert isinstance(text, str)
    for version in full:
        assert f"## Version {version.version}\n" in text
    assert text.count("- status: inactive") == 7
    assert text.count("- status: active") == 1
    assert "Abschnitt 0" not in text
    assert '"props"' not in text


def test_list_versions_text_format_omits_persona_modes_and_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persona-Historie: weder Profil-Bloecke noch Modus-Bloecke im Text.

    Die Modus-Felder (`identity_add` usw.) sind Block-Listen und waren die
    Luecke aus ADR-0056 Abschnitt 1.2: der fruehere `text`-Zuschnitt leerte
    nur das Profil. Unter Markdown traegt die Liste nur Koepfe.
    """
    entity_id = uuid4()
    content = _persona_payload(uuid4(), _fat_blocks(60))["content"]
    payload = [
        {
            "id": str(uuid4()),
            "version": version,
            "status": "inactive",
            "locale": "de",
            "content": content,
            "created_by": str(uuid4()),
            "created_at": "2026-01-01T00:00:00Z",
        }
        for version in range(1, 9)
    ]

    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=payload))
    )

    full = asyncio.run(list_versions("persona", str(entity_id), format="full"))
    text = asyncio.run(list_versions("persona", str(entity_id), format="text"))

    _assert_text_path_fits(full, text, "list_versions(persona)")
    assert isinstance(text, str)
    assert text.count("## Version ") == 8
    assert "Veredelungs-Haltung" not in text
    assert "Abschnitt 0" not in text
    assert '"props"' not in text


def _resource_payload(blocks: list[dict[str, object]], name: str = "Doc") -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": name,
        "slug": name.lower(),
        "current_version": 1,
        "current_status": "active",
        "has_pending_draft": False,
        "locale": "de",
        "content": {"description": "Referenz", "blocks": blocks, "tags": ["doku"]},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _template_payload(name: str, body: str) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "current_version": 1,
        "current_status": "active",
        "has_pending_draft": False,
        "locale": "de",
        "content": {"description": f"Beschreibung von {name}", "body": body},
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _external_tool_payload(name: str, usage_notes: str) -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "workspace_id": str(_WORKSPACE_ID),
        "owner_id": str(uuid4()),
        "name": name,
        "alias": name.lower(),
        "current_version": 1,
        "is_managed": False,
        "current_status": "active",
        "has_pending_draft": False,
        "locale": "de",
        "content": {
            "display_name": name,
            "mcp_server_name": f"{name} MCP",
            "tool_names": ["add_task"],
            "usage_notes": usage_notes,
            "fallback_note": None,
            "tags": [],
        },
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def test_fetch_resource_text_format_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Inhalt der Resource kommt als Text, ohne die Editor-Struktur."""
    resource = _resource_payload(_fat_blocks(250))
    resource_id = resource["id"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/sub_resources"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=resource)

    monkeypatch.setattr(server, "build_client", _factory(handler))

    full = asyncio.run(fetch_resource(str(resource_id), format="full"))
    text = asyncio.run(fetch_resource(str(resource_id), format="text"))

    _assert_text_path_fits(full, text, "fetch_resource")
    assert isinstance(text, str)
    assert "Abschnitt 249: Profiltext dieses Absatzes." in text
    assert '"props"' not in text


def test_get_system_prompt_text_format_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Body nahe am Maximum reisst nur als escapter JSON-String die Grenze.

    Das Fixture bleibt unter `max_length` des Bodys: der Fall, den
    `test_system_prompt_body_cannot_be_emptied_for_a_cheap_response` als
    strukturell beschreibt, ist unter `text` loesbar, weil der Text den Body
    ohne Editor-Struktur traegt statt ihn zu leeren.
    """
    template = _template_payload("Agent-Builder", _fat_blocknote_body(200))

    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=template))
    )

    full = asyncio.run(get_system_prompt(str(template["id"]), format="full"))
    text = asyncio.run(get_system_prompt(str(template["id"]), format="text"))

    _assert_text_path_fits(full, text, "get_system_prompt")
    assert isinstance(text, str)
    assert "Abschnitt 199: Profiltext dieses Absatzes." in text
    assert '"props"' not in text


def test_list_system_prompts_text_format_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Katalog traegt Kopf und Beschreibung, nicht die Bodies."""
    body = _fat_blocknote_body(100)
    payload = [_template_payload(f"Template {index}", body) for index in range(3)]

    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=payload))
    )

    full = asyncio.run(list_system_prompts(format="full"))
    text = asyncio.run(list_system_prompts(format="text"))

    _assert_text_path_fits(full, text, "list_system_prompts")
    assert isinstance(text, str)
    assert text.startswith("# System-Prompts (3)\n")
    for item in payload:
        assert f"- id: {item['id']}" in text
    assert "Abschnitt 0" not in text


def test_list_external_tools_text_format_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Katalog traegt Kopf und Felder, nicht die Nutzungshinweise."""
    notes = _fat_blocknote_body(80)
    payload = [_external_tool_payload(f"Tool{index}", notes) for index in range(4)]

    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=payload))
    )

    full = asyncio.run(list_external_tools(format="full"))
    text = asyncio.run(list_external_tools(format="text"))

    _assert_text_path_fits(full, text, "list_external_tools")
    assert isinstance(text, str)
    assert text.startswith("# Externe Tools (4)\n")
    assert text.count("- alias: tool") == 4
    assert "Abschnitt 0" not in text


def test_get_external_tool_text_format_drops_editor_json_at_max_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine einzelne Bindung kann die Grenze nicht reissen, also ohne Rot-Probe ueber `full`.

    `usage_notes` ist auf 20.000 Zeichen begrenzt; selbst escaped bleibt die
    `full`-Antwort darunter. Belegt wird deshalb: am Maximum kommt der Text an,
    er traegt den Inhalt und kein Editor-JSON, und er ist kleiner als `full`.
    """
    max_notes = ExternalToolContent.model_fields["usage_notes"].metadata
    limit = next(m.max_length for m in max_notes if getattr(m, "max_length", None) is not None)
    notes = _fat_blocknote_body(80)
    assert len(notes) <= limit, "Fixture ueber dem Feld-Maximum"
    tool = _external_tool_payload("Todoist", notes)

    monkeypatch.setattr(server, "build_client", _factory(lambda _r: httpx.Response(200, json=tool)))

    full = asyncio.run(get_external_tool(str(tool["id"]), format="full"))
    text = asyncio.run(get_external_tool(str(tool["id"]), format="text"))

    assert isinstance(text, str)
    assert _chars(text) <= _RESPONSE_CHAR_LIMIT
    assert _chars(text) < _chars(full) / 3
    assert "Abschnitt 79: Profiltext dieses Absatzes." in text
    assert '"props"' not in text


def test_get_version_text_format_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Snapshot nahe am Body-Maximum kommt als Text an."""
    entity_id = uuid4()
    snapshot = {
        "id": str(uuid4()),
        "version": 3,
        "status": "active",
        "locale": "de",
        "content": {
            "description": "Stand 3",
            "body": _fat_blocknote_body(200),
            "type": "workflow",
        },
        "created_by": str(uuid4()),
        "created_at": "2026-01-01T00:00:00Z",
    }

    monkeypatch.setattr(
        server, "build_client", _factory(lambda _r: httpx.Response(200, json=snapshot))
    )

    full = asyncio.run(get_version("playbook", str(entity_id), 3, format="full"))
    text = asyncio.run(get_version("playbook", str(entity_id), 3, format="text"))

    _assert_text_path_fits(full, text, "get_version")
    assert isinstance(text, str)
    assert "Abschnitt 199: Profiltext dieses Absatzes." in text
    assert '"props"' not in text


def test_diff_versions_text_format_stays_under_response_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Diff verliert die Rohwerte, der lesbare Vergleich bleibt."""
    entity_id = uuid4()
    blocks = _fat_blocks(100)
    readable = "\n\n".join(f"Abschnitt {i}: Profiltext dieses Absatzes." for i in range(100))
    diff = {
        "version": 2,
        "against": "active",
        "against_version": 1,
        "changes": [
            {"path": "content.blocks", "op": "changed", "before": blocks, "after": blocks[1:]}
        ],
        "identical": False,
        "before_text": readable,
        "after_text": readable.split("\n\n", 1)[1],
    }

    monkeypatch.setattr(server, "build_client", _factory(lambda _r: httpx.Response(200, json=diff)))

    full = asyncio.run(diff_versions("resource", str(entity_id), 2, format="full"))
    text = asyncio.run(diff_versions("resource", str(entity_id), 2, format="text"))

    _assert_text_path_fits(full, text, "diff_versions")
    assert isinstance(text, str)
    assert "- changed `content.blocks`" in text
    assert "## Vorher\n\nAbschnitt 0: Profiltext dieses Absatzes." in text
    assert '"props"' not in text


_PACKAGE_4_TOOLS: dict[str, Callable[..., object]] = {
    "fetch_resource": lambda fmt: fetch_resource(str(uuid4()), format=fmt),
    "get_system_prompt": lambda fmt: get_system_prompt(str(uuid4()), format=fmt),
    "list_system_prompts": lambda fmt: list_system_prompts(format=fmt),
    "get_external_tool": lambda fmt: get_external_tool("todo", format=fmt),
    "list_external_tools": lambda fmt: list_external_tools(format=fmt),
    "list_versions": lambda fmt: list_versions("playbook", str(uuid4()), format=fmt),
    "get_version": lambda fmt: get_version("playbook", str(uuid4()), 1, format=fmt),
    "diff_versions": lambda fmt: diff_versions("playbook", str(uuid4()), 1, format=fmt),
}


@pytest.mark.parametrize("tool", sorted(_PACKAGE_4_TOOLS))
def test_package_4_tools_reject_unknown_format(tool: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Tippfehler im `format` faellt auf, bevor die API gefragt wird."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(500, json={"detail": "darf nicht erreicht werden"})

    monkeypatch.setattr(server, "build_client", _factory(handler))
    with pytest.raises(ToolError, match="Ungueltiges format"):
        asyncio.run(_PACKAGE_4_TOOLS[tool]("plain"))  # type: ignore[arg-type]
    assert calls == []

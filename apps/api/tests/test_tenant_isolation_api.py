"""Mandantentrennung je Endpunkt: jede REST-Route als Mandant A mit IDs von B.

ADR-0055 §7 (Nachweisweg) und Owner-Entscheidung 2026-09-30 (Mandantentrennung
= b): die manuelle IDOR-Stichprobe aus dem Audit vom 2026-09-30 wird zum
CI-Gate ueber **alle** Routen. Der Test besteht aus zwei Teilen.

**1. Inventar (ohne DB).** Jede Route aus dem Router-Baum steht in `PROBES`
(geprueft) oder in `EXEMPT` (mit Begruendung). Eine neue Route ohne Eintrag
macht den Test rot, ebenso ein Eintrag ohne Route. So kann niemand eine Route
hinzufuegen, ohne sich zu ihrer Mandantentrennung zu verhalten.

**2. Lauf (mit DB).** Zwei Mandanten A und B mit identischem Bestand
(`who2be_api.testing.tenant_pair`). Je Route bis zu drei Varianten:

* **V1 fremder Workspace** — workspace-gebundene Route mit `wsB` im Pfad und
  B-IDs. Erwartet 403/404.
* **V2 fremde Objekt-ID** — eigener Workspace (`wsA`), Objekt-IDs von B im
  Pfad, in der Query oder im Body. Hat die Route Objekt-IDs im Pfad UND
  Referenzen im Body, laeuft zusaetzlich die Mischform: eigenes Objekt im
  Pfad, fremde Referenz im Body (z. B. B-Playbook an A-Persona haengen).
  Erwartet 403/404, eine Ausnahme nur mit Begruendung am Eintrag.
* **V3 Listen-Scan** — lesende Route ohne Objekt-Referenz im eigenen
  Workspace. Erwartet 2xx, und die Antwort enthaelt nichts von B.

Fuer **jede** Antwort an A gilt zusaetzlich: kein Marker und keine ID von B
im Antworttext, ausser A hat die ID selbst gesendet (Fehlermeldungen duerfen
die Anfrage zitieren). Und nach allen A-Aufrufen ist der Fingerabdruck von B
(Hash ueber alle Zeilen mit B-`workspace_id`/`org_id`) unveraendert: kein
Aufruf hat bei B geschrieben, auch nicht still hinter einer 404.

**Gegenprobe.** Jeder Aufruf aus V1/V2 laeuft danach als B mit B-IDs im
eigenen Workspace und muss gelingen. Erst damit ist eine 404 von A ein Befund
an der Mandantengrenze statt einer kaputten Probe (falscher Body, falsche
Rolle). Loeschende Aufrufe laufen in der Gegenprobe zuletzt, in fester
Reihenfolge, damit sie den Bestand der uebrigen Gegenproben nicht wegnehmen.

**Null geprueft ist rot.** Der Lauf sichert Mindestzahlen je Variante zu;
ein leerer Lauf (Inventar leer, Varianten ausgefiltert) kann nicht gruen sein.

Billing-Routen sind nur in der Cloud-Edition montiert und erscheinen in
diesem Lauf (On-Prem-Default) nicht im Router-Baum.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from who2be_api.main import app
from who2be_api.testing.api_helpers import db_execute, db_fetchval
from who2be_api.testing.tenant_pair import (
    ANCHOR_DENIED,
    DENIED,
    TABLE_SCHEMA,
    Tenant,
    control_passes,
    fingerprint,
    ghost_of,
    isolation_stores,
    leaks,
    seed_tenant,
)
from who2be_api.testing.workspace_setup import cleanup_workspaces, seed_auth_user

_WS = "/v1/workspaces/{workspace_id}"
# Pfad-Parameter, die keine Objekt-ID sind: der Workspace selbst (V1) und
# Literale, die je Probe fest gesetzt werden.
_NON_OBJECT_PARAMS = frozenset({"workspace_id", "version", "entity_type", "source_name"})
_REF = re.compile(r"<<([a-z0-9_]+)>>")


@dataclass(frozen=True)
class Probe:
    """Wie eine Route aufgerufen wird.

    `body`/`query` sind Vorlagen; `<<key>>` wird durch die ID des jeweiligen
    Mandanten ersetzt und macht das Feld zu einer Objekt-Referenz (V2).
    `path` setzt Pfad-Parameter, die nicht gleichnamig in `Tenant.ids`
    stehen (`entity_type`, Aliase wie `entity_id -> playbook_id`).
    `agent=True`: als agent-gebundener Token statt als Mensch — fuer Routen,
    die nur Agenten bedienen.
    `filters=True`: die Referenzen in Query/Body filtern eine Liste oder
    Suche statt ein Objekt zu adressieren. Eine fremde ID darf dann 2xx mit
    leerem Ergebnis liefern; entscheidend sind Leck-Check und Orakel-Vergleich.
    `known`: bekannter, noch offener Defekt dieser Route mit Verweis auf die
    Folgekarte. Er lockert Orakel- und Gegenprobe fuer genau diese Route.
    Verschwindet die Abweichung, wird der Test rot, damit der Eintrag geht.
    `oracle_exempt`: Begruendung, warum unterschiedliche Antworten fuer
    fremde und unbekannte IDs hier kein Orakel sind (etwa weil die "ID" ein
    Geheimnis ist, das nur der Berechtigte kennt).
    """

    body: Any = None
    query: dict[str, Any] | None = None
    path: dict[str, str] = field(default_factory=dict)
    agent: bool = False
    filters: bool = False
    known: str = ""
    oracle_exempt: str = ""
    denied: frozenset[int] = DENIED


_TEXT_FILE = base64.b64encode(b"Isolation probe text.").decode()
_CONTENT_PERSONA = {"description": "x", "system_prompt": "x", "content": {"blocks": []}}
_CONTENT_PLAYBOOK = {"description": "x", "body": "1. x", "type": "workflow"}
_CONTENT_RESOURCE = {"description": "x", "blocks": []}
_CONTENT_TOOL = {"display_name": "x", "mcp_server_name": "x", "tool_names": ["t"]}
_CONTENT_TEMPLATE = {"description": "", "body": "x"}
_TRANSITION = {"to": "review"}
_FEEDBACK_REF = {"entity_type": "playbook", "entity_id": "<<playbook_id>>"}

# Jede Route: Schluessel "METHOD Pfad" (Pfad wie im Router-Baum).
PROBES: dict[str, Probe] = {
    # --- Workspace selbst --------------------------------------------------
    f"GET {_WS}": Probe(),
    f"PATCH {_WS}": Probe(body={"name": "iso"}),
    f"DELETE {_WS}": Probe(),
    f"GET {_WS}/whoami": Probe(),
    f"GET {_WS}/dashboard": Probe(),
    f"GET {_WS}/billing/entitlement": Probe(),
    f"GET {_WS}/members": Probe(),
    f"PATCH {_WS}/members/{{user_id}}": Probe(body={"role": "viewer"}),
    f"DELETE {_WS}/members/{{user_id}}": Probe(),
    # Admin-Loeschen des Nutzergedaechtnisses (6.4.1 W5 = a, C3c-2b). Im
    # eigenen Workspace ergibt eine fremde Person `{deleted: 0}` wie eine
    # unbekannte (bewusst ohne Mitgliedschaftspruefung, das Gedaechtnis
    # ueberlebt den Austritt) — deshalb `filters`. Das Mitglied von B traegt
    # ein eigenes Nutzergedaechtnis (`member_memory_id`), damit der
    # Fingerabdruck ein Loeschen ueber die Workspace-Grenze sieht.
    f"DELETE {_WS}/members/{{user_id}}/memories": Probe(filters=True),
    f"GET {_WS}/invitations": Probe(),
    f"POST {_WS}/invitations": Probe(body={"email": "iso-probe@example.com", "role": "viewer"}),
    f"DELETE {_WS}/invitations/{{invitation_id}}": Probe(),
    f"GET {_WS}/tokens": Probe(query={"agent_id": "<<agent_id>>"}),
    f"POST {_WS}/tokens": Probe(body={"name": "iso", "agent_id": "<<agent_id>>"}),
    f"PATCH {_WS}/tokens/{{token_id}}": Probe(body={"name": "iso"}),
    f"POST {_WS}/tokens/{{token_id}}/rotate": Probe(),
    f"DELETE {_WS}/tokens/{{token_id}}": Probe(),
    # --- Personas ----------------------------------------------------------
    f"GET {_WS}/personas": Probe(query={"agent": "<<agent_id>>"}),
    f"POST {_WS}/personas": Probe(body={"name": "iso", "content": _CONTENT_PERSONA}),
    f"GET {_WS}/personas/tags": Probe(),
    f"GET {_WS}/personas/{{persona_id}}": Probe(),
    f"PUT {_WS}/personas/{{persona_id}}": Probe(body={"content": _CONTENT_PERSONA}),
    f"PATCH {_WS}/personas/{{persona_id}}/draft": Probe(body={"content": _CONTENT_PERSONA}),
    f"DELETE {_WS}/personas/{{persona_id}}": Probe(),
    f"POST {_WS}/personas/{{persona_id}}/duplicate": Probe(),
    f"GET {_WS}/personas/{{persona_id}}/export": Probe(),
    f"GET {_WS}/personas/{{persona_id}}/rendered": Probe(),
    f"GET {_WS}/personas/{{persona_id}}/playbooks": Probe(),
    f"PUT {_WS}/personas/{{persona_id}}/playbooks": Probe(
        body={"playbook_ids": ["<<playbook_id>>"]}
    ),
    f"GET {_WS}/personas/{{persona_id}}/versions": Probe(),
    f"GET {_WS}/personas/{{persona_id}}/versions/{{version}}": Probe(),
    f"GET {_WS}/personas/{{persona_id}}/versions/{{version}}/diff": Probe(),
    f"GET {_WS}/personas/{{persona_id}}/versions/{{version}}/provenance": Probe(),
    f"POST {_WS}/personas/{{persona_id}}/versions/{{version}}/restore": Probe(),
    f"POST {_WS}/personas/{{persona_id}}/versions/{{version}}/transition": Probe(body=_TRANSITION),
    # --- Playbooks ---------------------------------------------------------
    f"GET {_WS}/playbooks": Probe(query={"agent": "<<agent_id>>"}),
    f"POST {_WS}/playbooks": Probe(body={"name": "iso", "content": _CONTENT_PLAYBOOK}),
    f"GET {_WS}/playbooks/tags": Probe(),
    f"GET {_WS}/playbooks/triggers": Probe(),
    f"GET {_WS}/playbooks/{{playbook_id}}": Probe(),
    f"PUT {_WS}/playbooks/{{playbook_id}}": Probe(body={"content": _CONTENT_PLAYBOOK}),
    f"PATCH {_WS}/playbooks/{{playbook_id}}/draft": Probe(body={"content": _CONTENT_PLAYBOOK}),
    f"DELETE {_WS}/playbooks/{{playbook_id}}": Probe(),
    f"GET {_WS}/playbooks/{{playbook_id}}/export": Probe(),
    f"GET {_WS}/playbooks/{{playbook_id}}/rendered": Probe(),
    f"GET {_WS}/playbooks/{{playbook_id}}/usages": Probe(),
    f"GET {_WS}/playbooks/{{playbook_id}}/composes": Probe(),
    f"PUT {_WS}/playbooks/{{playbook_id}}/composes": Probe(
        body={"child_ids": ["<<child_playbook_id>>"]}
    ),
    f"GET {_WS}/playbooks/{{playbook_id}}/composed_by": Probe(),
    f"GET {_WS}/playbooks/{{playbook_id}}/resource_links": Probe(),
    f"PUT {_WS}/playbooks/{{playbook_id}}/resource_links": Probe(
        body={
            "links": [{"resource_id": "<<resource_id>>", "position": 0, "link_scope": "resource"}]
        }
    ),
    f"GET {_WS}/playbooks/{{playbook_id}}/versions": Probe(),
    f"GET {_WS}/playbooks/{{playbook_id}}/versions/{{version}}": Probe(),
    f"GET {_WS}/playbooks/{{playbook_id}}/versions/{{version}}/diff": Probe(),
    f"GET {_WS}/playbooks/{{playbook_id}}/versions/{{version}}/provenance": Probe(),
    f"POST {_WS}/playbooks/{{playbook_id}}/versions/{{version}}/restore": Probe(),
    f"POST {_WS}/playbooks/{{playbook_id}}/versions/{{version}}/transition": Probe(
        body=_TRANSITION
    ),
    # --- Resources ---------------------------------------------------------
    f"GET {_WS}/resources": Probe(query={"agent": "<<agent_id>>"}),
    f"POST {_WS}/resources": Probe(body={"name": "iso", "content": _CONTENT_RESOURCE}),
    f"GET {_WS}/resources/tags": Probe(),
    f"GET {_WS}/resources/{{resource_id}}": Probe(),
    f"PUT {_WS}/resources/{{resource_id}}": Probe(body={"content": _CONTENT_RESOURCE}),
    f"PATCH {_WS}/resources/{{resource_id}}/draft": Probe(body={"content": _CONTENT_RESOURCE}),
    f"DELETE {_WS}/resources/{{resource_id}}": Probe(),
    f"POST {_WS}/resources/{{resource_id}}/duplicate": Probe(),
    f"GET {_WS}/resources/{{resource_id}}/export": Probe(),
    f"GET {_WS}/resources/{{resource_id}}/blocks": Probe(),
    f"GET {_WS}/resources/{{resource_id}}/usages": Probe(),
    f"GET {_WS}/resources/{{resource_id}}/used_by": Probe(),
    f"GET {_WS}/resources/{{resource_id}}/sub_resources": Probe(),
    f"PUT {_WS}/resources/{{resource_id}}/sub_resources": Probe(
        body={"links": [{"child_id": "<<child_resource_id>>"}]}
    ),
    f"GET {_WS}/resources/{{resource_id}}/versions": Probe(),
    f"GET {_WS}/resources/{{resource_id}}/versions/{{version}}": Probe(),
    f"GET {_WS}/resources/{{resource_id}}/versions/{{version}}/diff": Probe(),
    f"GET {_WS}/resources/{{resource_id}}/versions/{{version}}/provenance": Probe(),
    f"POST {_WS}/resources/{{resource_id}}/versions/{{version}}/restore": Probe(),
    f"POST {_WS}/resources/{{resource_id}}/versions/{{version}}/transition": Probe(
        body=_TRANSITION
    ),
    # --- External Tools ----------------------------------------------------
    f"GET {_WS}/external_tools": Probe(),
    f"POST {_WS}/external_tools": Probe(body={"name": "iso", "content": _CONTENT_TOOL}),
    f"GET {_WS}/external_tools/{{tool_id}}": Probe(),
    f"PUT {_WS}/external_tools/{{tool_id}}": Probe(body={"content": _CONTENT_TOOL}),
    f"PATCH {_WS}/external_tools/{{tool_id}}/draft": Probe(body={"content": _CONTENT_TOOL}),
    f"DELETE {_WS}/external_tools/{{tool_id}}": Probe(),
    f"GET {_WS}/external_tools/{{tool_id}}/export": Probe(),
    f"GET {_WS}/external_tools/{{tool_id}}/versions": Probe(),
    f"GET {_WS}/external_tools/{{tool_id}}/versions/{{version}}": Probe(),
    f"GET {_WS}/external_tools/{{tool_id}}/versions/{{version}}/provenance": Probe(),
    f"POST {_WS}/external_tools/{{tool_id}}/versions/{{version}}/restore": Probe(),
    f"POST {_WS}/external_tools/{{tool_id}}/versions/{{version}}/transition": Probe(
        body=_TRANSITION
    ),
    # --- System-Prompt-Templates -------------------------------------------
    f"GET {_WS}/system-prompts": Probe(),
    f"POST {_WS}/system-prompts": Probe(body={"name": "iso", "content": _CONTENT_TEMPLATE}),
    f"GET {_WS}/system-prompts/{{template_id}}": Probe(),
    f"PUT {_WS}/system-prompts/{{template_id}}": Probe(body={"content": _CONTENT_TEMPLATE}),
    f"POST {_WS}/system-prompts/{{template_id}}/duplicate": Probe(),
    f"GET {_WS}/system-prompts/{{template_id}}/versions": Probe(),
    f"GET {_WS}/system-prompts/{{template_id}}/versions/{{version}}": Probe(),
    f"GET {_WS}/system-prompts/{{template_id}}/versions/{{version}}/diff": Probe(),
    f"GET {_WS}/system-prompts/{{template_id}}/versions/{{version}}/provenance": Probe(),
    f"POST {_WS}/system-prompts/{{template_id}}/versions/{{version}}/restore": Probe(),
    f"POST {_WS}/system-prompts/{{template_id}}/versions/{{version}}/transition": Probe(
        body=_TRANSITION
    ),
    # --- Agenten -----------------------------------------------------------
    f"GET {_WS}/agents": Probe(),
    f"POST {_WS}/agents": Probe(
        body={
            "name": "iso",
            "persona_id": "<<persona_id>>",
            "system_prompt_template_id": "<<template_id>>",
        }
    ),
    f"GET {_WS}/agents/{{agent_id}}": Probe(),
    f"PUT {_WS}/agents/{{agent_id}}": Probe(body={"persona_id": "<<persona_id>>"}),
    f"DELETE {_WS}/agents/{{agent_id}}": Probe(),
    f"POST {_WS}/agents/{{agent_id}}/copy": Probe(body={}),
    f"PUT {_WS}/agents/{{agent_id}}/favorite": Probe(),
    f"DELETE {_WS}/agents/{{agent_id}}/favorite": Probe(),
    f"GET {_WS}/agents/{{agent_id}}/render": Probe(),
    f"GET {_WS}/agents/{{agent_id}}/rendered": Probe(),
    f"GET {_WS}/agents/{{agent_id}}/memories": Probe(),
    f"PUT {_WS}/agents/{{agent_id}}/memories/{{memory_id}}": Probe(body={"fact": "iso"}),
    f"POST {_WS}/agents/{{agent_id}}/memories/{{memory_id}}/triage": Probe(
        body={"action": "reject"}
    ),
    # Einzel-Loeschung vor der Sammel-Loeschung: die Gegenprobe laeuft in
    # dieser Reihenfolge, und danach gaebe es die Einzel-Memory nicht mehr.
    f"DELETE {_WS}/agents/{{agent_id}}/memories/{{memory_id}}": Probe(),
    f"DELETE {_WS}/agents/{{agent_id}}/memories": Probe(),
    # Historie/Rollback/Bestaetigen (ADR-0053 6.4, C3b). Das Ereignis ist ein
    # `created` ohne Vorzustand: die Gegenprobe endet fachlich mit 409 nach
    # dem Lookup, die fremde Referenz im Body (V2-mix) an der Zugehoerigkeit.
    f"GET {_WS}/agents/{{agent_id}}/memories/{{memory_id}}/history": Probe(),
    f"POST {_WS}/agents/{{agent_id}}/memories/{{memory_id}}/rollback": Probe(
        body={"event_id": "<<memory_event_id>>"}
    ),
    f"POST {_WS}/agents/{{agent_id}}/memories/{{memory_id}}/confirm": Probe(),
    f"POST {_WS}/agents/{{agent_id}}/memories/{{memory_id}}/reactivate": Probe(),
    # --- Vorschlaege (3.1.4); IDs setzt `_memory_extras` ---------------------
    f"POST {_WS}/agent-memory-proposals": Probe(
        body={"memory_id": "<<active_memory_id>>", "action": "delete", "reason": "iso"},
        agent=True,
    ),
    f"GET {_WS}/agents/{{agent_id}}/memory-proposals": Probe(),
    f"GET {_WS}/memory-proposals": Probe(query={"agent_id": "<<agent_id>>"}),
    f"POST {_WS}/memory-proposals/{{proposal_id}}/decide": Probe(body={"accept": False}),
    # Workspace-weite Liste und Zaehler (6.4.1, C3c-1b): `agent_id` ist die
    # Objekt-Referenz; ein fremder Agent ist `agent_not_found` (V1/V2).
    f"GET {_WS}/memories": Probe(query={"agent_id": "<<agent_id>>"}),
    f"GET {_WS}/memories/counts": Probe(
        query={"agent_id": "<<agent_id>>", "group_by": ["agent", "status"]}
    ),
    # Einzelabruf (t_ef8822fa): fremde Memory-ID ist `memory_not_found` (V1/V2),
    # das eigene Agentengedaechtnis in der Gegenprobe 200.
    f"GET {_WS}/memories/{{memory_id}}": Probe(),
    # Stapel (6.4.1, C3c-2b): die IDs im Body waehlen aus, statt die Route zu
    # adressieren. Eine fremde ID ist je Eintrag `memory_not_found` (200, wie
    # eine unbekannte) — deshalb `filters`; der Fingerabdruck belegt, dass bei
    # B nichts geaendert wurde.
    f"POST {_WS}/memories/batch": Probe(
        body={"action": "reject", "ids": ["<<memory_id>>"]}, filters=True
    ),
    # Not-Aus (6.4.1, C3b-2b): `agent_id` ist die Objekt-Referenz (V1/V2).
    # `dry_run`, damit die Gegenprobe den Bestand von B nicht zuruecknimmt.
    f"POST {_WS}/memories/revoke-auto": Probe(
        body={"since": "2020-01-01T00:00:00Z", "agent_id": "<<agent_id>>", "dry_run": True}
    ),
    # --- Eigenes Nutzergedaechtnis (3.1.1) ---------------------------------
    f"GET {_WS}/me/memories": Probe(),
    f"POST {_WS}/me/memories/{{memory_id}}/triage": Probe(
        body={"action": "reject"}, path={"memory_id": "user_memory_id"}
    ),
    f"PUT {_WS}/me/memories/{{memory_id}}": Probe(
        body={"fact": "iso"}, path={"memory_id": "user_memory_id"}
    ),
    f"GET {_WS}/me/memories/{{memory_id}}/history": Probe(path={"memory_id": "user_memory_id"}),
    f"POST {_WS}/me/memories/{{memory_id}}/rollback": Probe(
        body={"event_id": "<<user_memory_event_id>>"}, path={"memory_id": "user_memory_id"}
    ),
    f"POST {_WS}/me/memories/{{memory_id}}/confirm": Probe(path={"memory_id": "user_memory_id"}),
    f"POST {_WS}/me/memories/{{memory_id}}/reactivate": Probe(path={"memory_id": "user_memory_id"}),
    f"DELETE {_WS}/me/memories/{{memory_id}}": Probe(path={"memory_id": "user_memory_id"}),
    # --- Agenten-Gedaechtnis (nur Agent-Token) -----------------------------
    f"GET {_WS}/agent-memories": Probe(agent=True),
    f"POST {_WS}/agent-memories": Probe(
        body={"fact": "Nutzer mag Gruen", "origin": "user_stated"}, agent=True
    ),
    f"GET {_WS}/agent-memories/search": Probe(
        query={"query": "<<marker>>"}, agent=True, filters=True
    ),
    f"GET {_WS}/memory-guard": Probe(),
    f"PUT {_WS}/memory-guard": Probe(body={"mode": "standard"}),
    f"GET {_WS}/memory-auto-policy": Probe(),
    f"PUT {_WS}/memory-auto-policy": Probe(body={"enabled_cells": []}),
    # --- Feedback / Nutzung ------------------------------------------------
    f"POST {_WS}/usage-events": Probe(body=_FEEDBACK_REF, agent=True),
    f"POST {_WS}/feedback": Probe(body={**_FEEDBACK_REF, "signal": "helpful"}, agent=True),
    f"POST {_WS}/system-feedback": Probe(body={"category": "other", "note": "iso"}, agent=True),
    f"GET {_WS}/feedback-items": Probe(),
    f"GET {_WS}/feedback-overview": Probe(),
    f"GET {_WS}/feedback-unused": Probe(),
    f"GET {_WS}/feedback/{{feedback_id}}": Probe(),
    f"DELETE {_WS}/feedback/{{feedback_id}}": Probe(),
    f"POST {_WS}/feedback/{{feedback_id}}/resolution": Probe(body={"resolution": "dismissed"}),
    f"GET {_WS}/feedback/{{entity_type}}/{{entity_id}}": Probe(
        path={"entity_type": "playbook", "entity_id": "playbook_id"}
    ),
    f"GET {_WS}/feedback/{{entity_type}}/{{entity_id}}/events": Probe(
        path={"entity_type": "playbook", "entity_id": "playbook_id"}
    ),
    # --- Pruefaelle --------------------------------------------------------
    f"GET {_WS}/test-cases": Probe(query={"agent_id": "<<agent_id>>"}, filters=True),
    f"POST {_WS}/test-cases": Probe(
        body={
            "agent_id": "<<agent_id>>",
            "title": "iso",
            "input": "x",
            "expected_behavior": "x",
        }
    ),
    f"GET {_WS}/test-cases/{{case_id}}": Probe(),
    f"POST {_WS}/test-cases/{{case_id}}/retire": Probe(),
    f"POST {_WS}/test-runs": Probe(
        body={
            "subject_entity_type": "persona",
            "subject_version_id": "<<version_id>>",
            "results": [
                {
                    "test_case_id": "<<case_id>>",
                    "runs_total": 1,
                    "runs_passed": 1,
                    "verdict": "pass",
                }
            ],
        },
        agent=True,
    ),
    f"GET {_WS}/versions/{{entity_type}}/{{version_id}}/test-report": Probe(
        path={"entity_type": "persona"}
    ),
    # --- Platzhalter / Suche -----------------------------------------------
    f"GET {_WS}/placeholders": Probe(),
    f"GET {_WS}/placeholders/preview": Probe(
        # Ein fremdes Ziel wird wie ein geloeschtes als "nicht verfuegbar"
        # gerendert (200, unresolved) — kein Orakel, solange A und ein
        # unbekanntes Ziel dieselbe Antwort sehen.
        query={"kind": "playbook", "target_id": "<<playbook_id>>"},
        filters=True,
    ),
    f"GET {_WS}/search": Probe(query={"q": "<<marker>>"}, filters=True),
    f"GET {_WS}/search/content": Probe(query={"q": "<<marker>>"}, filters=True),
    # --- Arbeitsbereich ----------------------------------------------------
    f"GET {_WS}/work-areas": Probe(),
    f"POST {_WS}/work-areas": Probe(body={"name": "iso"}),
    f"GET {_WS}/work-areas/{{area_id}}/artifacts": Probe(),
    f"POST {_WS}/work-areas/{{area_id}}/artifacts": Probe(
        body={"title": "iso", "content_md": "x", "occurred_at": "2026-08-01T00:00:00Z"}
    ),
    f"POST {_WS}/work-areas/{{area_id}}/ingest": Probe(
        body={"file_b64": _TEXT_FILE, "filename": "iso.txt"}
    ),
    f"GET {_WS}/work-areas/{{area_id}}/grants": Probe(),
    f"PUT {_WS}/work-areas/{{area_id}}/grants/{{agent_id}}": Probe(body={"level": "read"}),
    f"DELETE {_WS}/work-areas/{{area_id}}/grants/{{agent_id}}": Probe(),
    f"GET {_WS}/work-areas/{{area_id}}/category-rules": Probe(),
    f"POST {_WS}/work-areas/{{area_id}}/category-rules": Probe(
        body={"pattern": "iso", "category": "x"}
    ),
    f"GET {_WS}/work-areas/{{area_id}}/conventions": Probe(),
    f"PUT {_WS}/work-areas/{{area_id}}/conventions/{{source_name}}": Probe(
        body={"convention": {"decimal_separator": ","}}, path={"source_name": "bank"}
    ),
    f"GET {_WS}/work-areas/{{area_id}}/tables": Probe(),
    f"POST {_WS}/work-areas/{{area_id}}/tables": Probe(
        body={"name": "iso_probe", "schema": TABLE_SCHEMA}
    ),
    f"POST {_WS}/artifacts": Probe(
        body={"title": "iso", "content_md": "x", "occurred_at": "2026-08-01T00:00:00Z"},
        agent=True,
    ),
    f"POST {_WS}/ingest": Probe(body={"file_b64": _TEXT_FILE, "filename": "iso.txt"}, agent=True),
    f"GET {_WS}/wa-artifacts/{{artifact_id}}": Probe(),
    f"PATCH {_WS}/wa-artifacts/{{artifact_id}}": Probe(
        # Mischform: eigenes Artifact, fremder Block-Anker -> 422 wie unbekannt.
        body={"anchor": "<<block_id>>", "op": "replace", "content_md": "x", "expected_rev": 1},
        denied=ANCHOR_DENIED,
    ),
    f"DELETE {_WS}/wa-artifacts/{{artifact_id}}": Probe(),
    f"POST {_WS}/wa-artifacts/{{artifact_id}}/append": Probe(body={"content_md": "x"}),
    f"GET {_WS}/wa-artifacts/{{artifact_id}}/export": Probe(),
    f"POST {_WS}/wa-artifacts/{{artifact_id}}/promote": Probe(
        query={"target_resource_id": "<<resource_id>>"}
    ),
    f"GET {_WS}/wa-tables/{{table_id}}": Probe(),
    f"DELETE {_WS}/wa-tables/{{table_id}}": Probe(),
    f"GET {_WS}/wa-tables/{{table_id}}/export": Probe(),
    f"POST {_WS}/wa-tables/{{table_id}}/query": Probe(body={"sql": "SELECT 1"}),
    f"POST {_WS}/wa-tables/{{table_id}}/rows": Probe(
        body={"rows": [{"occurred_at": "2026-08-02T00:00:00+00:00", "amount": 2, "purpose": "x"}]}
    ),
    f"POST {_WS}/wa-tables/{{table_id}}/save-result": Probe(
        body={"sql": "SELECT 1", "title": "iso", "occurred_at": "2026-08-01T00:00:00Z"}
    ),
    f"GET {_WS}/workarea-search": Probe(query={"q": "<<marker>>"}, filters=True),
    f"GET {_WS}/timeline": Probe(
        query={
            "from_": "2026-01-01T00:00:00Z",
            "to": "2026-12-31T00:00:00Z",
            "sources": "table:<<table_id>>",
        }
    ),
    # --- Knowledge Base ----------------------------------------------------
    f"POST {_WS}/kb/nodes": Probe(
        body={
            "content": "iso",
            "tier": "hypothesis",
            "source_ref": "<<artifact_id>>#<<block_id>>",
            "occurred_at": "2026-08-01T00:00:00Z",
        },
        denied=ANCHOR_DENIED,
    ),
    f"GET {_WS}/kb/nodes/{{node_id}}": Probe(),
    f"PATCH {_WS}/kb/nodes/{{node_id}}": Probe(body={"content": "iso"}),
    f"POST {_WS}/kb/edges": Probe(
        body={
            "from_anchor": "node:<<node_id>>",
            "to_anchor": "node:<<node2_id>>",
            "type": "supports",
            "evidence_from": ["<<artifact_id>>#<<block_id>>"],
            "evidence_to": ["<<artifact_id>>#<<block_id>>"],
        },
        denied=ANCHOR_DENIED,
    ),
    f"GET {_WS}/kb/neighbors": Probe(query={"anchor": "node:<<node_id>>"}, denied=ANCHOR_DENIED),
    f"GET {_WS}/kb-search": Probe(query={"q": "<<marker>>"}, filters=True),
    # --- Kontoweite Routen -------------------------------------------------
    "GET /v1/me": Probe(),
    "GET /v1/organizations": Probe(),
    "GET /v1/gdpr/export": Probe(),
    "GET /v1/organizations/{organization_id}/workspaces": Probe(),
    "POST /v1/organizations/{organization_id}/workspaces": Probe(
        body={"name": "iso", "slug": "iso-probe"}
    ),
    "DELETE /v1/organizations/{organization_id}": Probe(),
    # Offene Einladungen des eigenen Kontos, ueber alle Workspaces hinweg —
    # genau deshalb hier: B hat eine offene Einladung auf B's Adresse, A darf
    # sie nicht sehen (V3, Leck-Check). Beide Konten sind bestaetigt
    # (`_confirm_accounts` in `run_isolation`), sonst antwortete die Route 403.
    "GET /v1/invitations/pending": Probe(),
    # Annahme per Klick: die ID einer Einladung an B's eigene Adresse. Als A
    # (andere, ebenfalls bestaetigte Adresse) muss sie wie eine unbekannte ID
    # mit 404 enden und B unveraendert lassen; die Gegenprobe (B nimmt die
    # eigene an) kommt durch. `own_invitation_id` setzt `_own_invitations`.
    "POST /v1/invitations/pending/{invitation_id}/accept": Probe(
        path={"invitation_id": "own_invitation_id"}
    ),
    # Der Einladungs-Token ist das Objekt: A haelt den Token einer Einladung
    # in B. Ohne passende E-Mail im Login muss die Annahme scheitern (L1).
    # Beide Annahmewege teilen den Service; der Body-Weg ist der Nachfolger.
    "POST /v1/invitations/accept": Probe(
        body={"token": "<<invite_token>>"},
        oracle_exempt=(
            "Der Token ist ein 256-Bit-Geheimnis aus der Einladungs-Mail. Wer ihn "
            "hat, darf wissen, dass er gilt (403 bei falscher E-Mail statt 404)."
        ),
    ),
    "POST /v1/invitations/{token}/accept": Probe(
        path={"token": "invite_token"},
        oracle_exempt=(
            "Der Token ist ein 256-Bit-Geheimnis aus der Einladungs-Mail. Wer ihn "
            "hat, darf wissen, dass er gilt (403 bei falscher E-Mail statt 404)."
        ),
    ),
}

EXEMPT: dict[str, str] = {
    "GET /v1/health": "Ohne Anmeldung, liefert nur Status und Version, keine Mandantendaten.",
    "GET /.well-known/oauth-authorization-server": (
        "Oeffentliche RFC-8414-Metadaten des Autorisierungsservers, keine Mandantendaten."
    ),
    "POST /oauth/register": "Dynamische Client-Registrierung (RFC 7591), keine Mandanten-Objekte.",
    "GET /oauth/authorize": (
        "Leitet nur auf die Consent-Seite um; die Agent-Bindung entsteht erst im Consent."
    ),
    "POST /oauth/token": (
        "Tausch eines Codes/Refresh-Tokens; das Geheimnis ist das Objekt, keine Objekt-ID. "
        "Mandantenbindung des Codes: test_oauth.py."
    ),
    "POST /oauth/consent": (
        "Verlangt einen signierten Autorisierungs-Request statt freier IDs; fremde Agenten "
        "und Nicht-Mitglieder deckt test_oauth.py::test_oauth_consent_rejects_non_member ab."
    ),
    "POST /oauth/consent/preview": (
        "Wie /oauth/consent; Orakel-Freiheit fuer fremde Agenten: "
        "test_oauth.py::test_consent_preview_is_no_existence_oracle."
    ),
    "POST /v1/organizations": "Legt eine neue eigene Organisation an, nimmt keine Objekt-ID.",
    "DELETE /v1/me": "Loescht das eigene Konto, nimmt keine Objekt-ID.",
}

# Gegenprobe: loeschende Aufrufe zuletzt und in dieser Reihenfolge — erst die
# Blaetter, dann Agent (entwertet den Agent-Token), Organisation, Workspace.
_DELETE_LAST = (
    f"DELETE {_WS}/agents/{{agent_id}}",
    "DELETE /v1/organizations/{organization_id}",
    f"DELETE {_WS}",
)


# --------------------------------------------------------------------------
# Inventar
# --------------------------------------------------------------------------


def _walk(routes: Any, prefix: str = "") -> Iterator[tuple[str, APIRoute]]:
    """Alle Routen mit vollem Pfad, rekursiv durch `_IncludedRouter` hindurch.

    Die FastAPI-Version dieses Repos legt in `app.routes` Wrapper ab; der
    Prefix steht im `include_context` des Wrappers, nicht am inneren Pfad
    (vgl. `test_gate_inventory.py`).
    """
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix + route.path, route
            continue
        inner = getattr(route, "original_router", None)
        if inner is not None:
            context = getattr(route, "include_context", None)
            yield from _walk(inner.routes, prefix + (getattr(context, "prefix", "") or ""))


def live_routes() -> dict[str, APIRoute]:
    found: dict[str, APIRoute] = {}
    for path, route in _walk(app.routes):
        for method in sorted((route.methods or set()) - {"HEAD"}):
            found[f"{method} {path}"] = route
    return found


def test_every_route_is_probed_or_exempt() -> None:
    """Neue Route ohne Eintrag oder Eintrag ohne Route: rot."""
    live = set(live_routes())
    assert len(live) > 150, f"Router-Baum unplausibel klein ({len(live)}) — Traversierung kaputt?"
    both = set(PROBES) & set(EXEMPT)
    assert not both, f"Route zugleich geprueft und ausgenommen: {sorted(both)}"
    missing = sorted(live - set(PROBES) - set(EXEMPT))
    assert not missing, (
        "Route(n) ohne Mandantentrennungs-Probe. In PROBES eintragen (wie wird sie mit "
        "fremden IDs aufgerufen?) oder mit Begruendung in EXEMPT:\n  " + "\n  ".join(missing)
    )
    stale = sorted((set(PROBES) | set(EXEMPT)) - live)
    assert not stale, f"Eintrag ohne Route (entfernen): {stale}"
    assert all(reason.strip() for reason in EXEMPT.values())


def test_probes_cover_every_path_parameter() -> None:
    """Jeder Objekt-Parameter im Pfad ist aufloesbar — sonst prueft V2 nichts."""
    from who2be_api.testing.tenant_pair import FULL_POLICY  # noqa: F401  (Import-Check)

    known = {
        "persona_id", "playbook_id", "resource_id", "tool_id", "template_id", "agent_id",
        "memory_id", "feedback_id", "case_id", "version_id", "area_id", "artifact_id",
        "table_id", "node_id", "token_id", "invitation_id", "user_id", "organization_id",
        "own_invitation_id", "user_memory_id", "proposal_id",
    }  # fmt: skip
    for key, probe in PROBES.items():
        for param in re.findall(r"{(\w+)}", key):
            if param in _NON_OBJECT_PARAMS and param not in probe.path:
                if param in ("workspace_id", "version"):
                    continue
                pytest.fail(f"{key}: Literal-Parameter {param} ohne Wert in Probe.path")
            target = probe.path.get(param, param)
            if param not in _NON_OBJECT_PARAMS:
                assert target in known or target == "invite_token", (key, param)


# --------------------------------------------------------------------------
# Lauf
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Call:
    """Ein konkreter Aufruf: wer, wohin, womit, und in welcher Variante."""

    key: str
    variant: str  # V1 | V2 | V2-mix | V3
    method: str
    url: str
    query: dict[str, Any] | None
    body: Any
    agent: bool


def _fill(template: Any, ids: dict[str, str]) -> Any:
    if isinstance(template, str):
        return _REF.sub(lambda m: ids[m.group(1)], template)
    if isinstance(template, list):
        return [_fill(v, ids) for v in template]
    if isinstance(template, dict):
        return {k: _fill(v, ids) for k, v in template.items()}
    return template


def _has_refs(template: Any) -> bool:
    return bool(_REF.search(json.dumps(template))) if template is not None else False


def _with_marker(t: Tenant) -> dict[str, str]:
    return {**t.ids, "marker": t.marker}


def _path(key: str, probe: Probe, ws: Tenant, obj: Tenant) -> str:
    path = key.split(" ", 1)[1]

    def repl(m: re.Match[str]) -> str:
        param = m.group(1)
        if param == "workspace_id":
            return str(ws.workspace_id)
        if param == "version":
            return "1"
        value = probe.path.get(param, param)
        return obj.ids.get(value, value)

    return re.sub(r"{(\w+)}", repl, path)


def build_calls(key: str, probe: Probe, me: Tenant, other: Tenant) -> list[Call]:
    """Die Varianten einer Route fuer `me` gegen `other` (siehe Moduldoku)."""
    method = key.split(" ", 1)[0]
    raw_path = key.split(" ", 1)[1]
    object_params = [p for p in re.findall(r"{(\w+)}", raw_path) if p not in _NON_OBJECT_PARAMS]
    refs = _has_refs(probe.body) or _has_refs(probe.query)
    on_ws = raw_path.startswith(_WS)
    mine, theirs = _with_marker(me), _with_marker(other)

    def call(variant: str, ws: Tenant, path_obj: Tenant, ref_ids: dict[str, str]) -> Call:
        return Call(
            key=key,
            variant=variant,
            method=method,
            url=_path(key, probe, ws, path_obj),
            query=_fill(probe.query, ref_ids),
            body=_fill(probe.body, ref_ids),
            agent=probe.agent,
        )

    calls: list[Call] = []
    if on_ws:
        calls.append(call("V1", other, other, theirs))
    if object_params:
        calls.append(call("V2", me, other, theirs))
    if refs:
        calls.append(call("V2-mix" if object_params else "V2", me, me, theirs))
    if not calls or (not object_params and not refs and method == "GET"):
        if method == "GET":
            calls.append(call("V3", me, me, mine))
    return calls


def _send(client: TestClient, c: Call, who: Tenant) -> Any:
    headers = who.agent if c.agent else who.human
    return client.request(c.method, c.url, params=c.query, json=c.body, headers=headers)


def _leaks(text: str, c: Call, other: Tenant) -> list[str]:
    """B-Spuren in der Antwort, ausgenommen was A selbst gesendet hat."""
    return leaks(text, c.url + json.dumps(c.query) + json.dumps(c.body), other)


@pytest.fixture
def isolation_env(tmp_path: Path) -> Iterator[None]:
    with isolation_stores(tmp_path):
        yield


def _confirm_accounts(*tenants: Tenant) -> None:
    """Bestaetigte Konten im `auth.users`-Stub, mit der Adresse aus dem JWT.

    `seed_tenant` setzt den `email`-Claim auf `<marker>@example.com` (klein)
    und laedt auf genau diese Adresse eine eigene Einladung ein. Ohne
    bestaetigtes Konto antwortete `GET /v1/invitations/pending` mit 403, und
    die V3-Probe saehe nie eine Liste.
    """
    for t in tenants:
        seed_auth_user(t.user_id, f"{t.marker.lower()}@example.com", None)
        db_execute("UPDATE auth.users SET email_confirmed_at = now() WHERE id = $1", t.user_id)


def _own_invitations(ghost: Tenant, *tenants: Tenant) -> None:
    """ID der Einladung, die `seed_tenant` auf die eigene Adresse ausstellt.

    Ziel der Annahme per Klick (`POST /v1/invitations/pending/{id}/accept`).
    `seed_tenant` gibt nur den Token heraus; die ID kommt deshalb aus der DB.
    Der Geist bekommt eine Zufalls-ID — seine IDs stehen schon fest, wenn
    dieser Lauf beginnt (`ghost_of` vor `run_isolation`).
    """
    for t in tenants:
        t.ids["own_invitation_id"] = str(
            db_fetchval(
                "SELECT id FROM workspace_invitation WHERE workspace_id = $1 AND email = $2",
                t.workspace_id,
                f"{t.marker.lower()}@example.com",
            )
        )
    ghost.ids["own_invitation_id"] = str(uuid4())


def _seed_memory(t: Tenant, fact: str, status: str, subject: object) -> str:
    """Eintrag mit Marker; `subject` gesetzt = Nutzergedaechtnis, sonst Agent."""
    return str(
        db_fetchval(
            "INSERT INTO agent_memory (workspace_id, agent_id, created_by_agent_id, "
            " status, fact, category, importance, kind, scope, origin, source, "
            " subject_user_id) "
            "VALUES ($1, CASE WHEN $5::uuid IS NULL THEN $2::uuid END, $2::uuid, $3, "
            "        $4, 'preference', 6, 'user_fact', "
            "        CASE WHEN $5::uuid IS NULL THEN 'agent' ELSE 'user' END, "
            "        'user_stated', 'agent', $5::uuid) RETURNING id",
            t.workspace_id,
            t.ids["agent_id"],
            status,
            f"{t.marker} {fact}",
            subject,
        )
    )


def _seed_created_event(t: Tenant, memory_id: str) -> str:
    return str(
        db_fetchval(
            "INSERT INTO agent_memory_event (workspace_id, memory_id, event, actor_kind, "
            " after) VALUES ($1, $2::uuid, 'created', 'system', '{}'::jsonb) RETURNING id",
            t.workspace_id,
            memory_id,
        )
    )


def _memory_extras(ghost: Tenant, *tenants: Tenant) -> None:
    """Gedaechtnis-Objekte fuer die C3b-Routen (ADR-0053 6.4), direkt in der DB.

    `seed_tenant` legt nur einen offenen Agenten-Eintrag an. Vorschlaege
    brauchen einen aktiven Eintrag, `/me/memories` einen Eintrag im
    Nutzergedaechtnis des Mandanten-Menschen, Rollback ein Ereignis. Alle
    Fakten tragen den Marker, damit ein Leck im Antworttext auffaellt.
    """
    for t in tenants:
        t.ids["memory_event_id"] = _seed_created_event(t, t.ids["memory_id"])
        t.ids["active_memory_id"] = _seed_memory(t, "Nutzer mag Ocker", "active", None)
        t.ids["proposal_id"] = str(
            db_fetchval(
                "INSERT INTO agent_memory_proposal (workspace_id, memory_id, agent_id, action, "
                " new_fact, reason) VALUES ($1, $2::uuid, $3::uuid, 'change', $4, 'iso') "
                "RETURNING id",
                t.workspace_id,
                t.ids["active_memory_id"],
                t.ids["agent_id"],
                f"{t.marker} Nutzer mag Umbra",
            )
        )
        t.ids["user_memory_id"] = _seed_memory(t, "Nutzer liest Krimis", "pending", t.user_id)
        t.ids["user_memory_event_id"] = _seed_created_event(t, t.ids["user_memory_id"])
        # Nutzergedaechtnis des zweiten Mitglieds: Ziel des Admin-Loeschens.
        t.ids["member_memory_id"] = _seed_memory(t, "Nutzer mag Moos", "active", t.ids["user_id"])
    for key in (
        "memory_event_id",
        "active_memory_id",
        "proposal_id",
        "user_memory_id",
        "user_memory_event_id",
        "member_memory_id",
    ):
        ghost.ids[key] = str(uuid4())


@pytest.mark.integration
@pytest.mark.usefixtures("migrated_db", "isolation_env")
def test_no_route_crosses_the_tenant_boundary(patched_jwt_secret: str) -> None:
    tenants: list[Tenant] = []
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            a = seed_tenant(client, "A", patched_jwt_secret)
            tenants.append(a)
            b = seed_tenant(client, "B", patched_jwt_secret)
            tenants.append(b)
            ghost = ghost_of(b)
            report = run_isolation(client, a, b, ghost)

        assert not report.findings, f"{len(report.findings)} Befund(e):\n" + "\n".join(
            report.findings
        )
        # Null geprueft ist rot: die Mindestzahlen liegen knapp unter dem
        # heutigen Stand und fallen nur, wenn Varianten verloren gehen.
        counts = report.counts
        assert counts.get("V1", 0) >= 170, counts
        assert counts.get("V2", 0) >= 140, counts
        assert counts.get("V2-mix", 0) >= 6, counts
        assert counts.get("V3", 0) >= 20, counts
        # V1- und V2-Gegenprobe sind derselbe Aufruf (B, eigene IDs) und
        # laufen nur einmal.
        assert counts.get("control", 0) >= 175, counts
    finally:
        cleanup_workspaces([t.user_id for t in tenants])


@dataclass
class Report:
    findings: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    known_seen: set[str] = field(default_factory=set)

    def count(self, what: str) -> None:
        self.counts[what] = self.counts.get(what, 0) + 1


def _probe_as_a(
    client: TestClient, report: Report, c: Call, g: Call | None, a: Tenant, b: Tenant
) -> None:
    """Ein fremder Aufruf als A: Abweisung, kein Leck, kein Existenz-Orakel."""
    probe = PROBES[c.key]
    response = _send(client, c, a)
    status = response.status_code
    report.count(c.variant)
    leaked = _leaks(response.text, c, b)
    if leaked:
        report.findings.append(f"{c.variant} {c.key}: B-Daten in Antwort an A: {leaked}")
    if status >= 500:
        report.findings.append(f"{c.variant} {c.key}: A -> {status} (Serverfehler)")
        return
    if c.variant == "V3":
        if not 200 <= status < 300:
            report.findings.append(f"V3 {c.key}: Liste/Suche als A -> {status}")
        return
    if 200 <= status < 300 and not probe.filters:
        report.findings.append(
            f"{c.variant} {c.key}: A mit B-IDs -> {status} (erwartet Abweisung) "
            f"{response.text[:200]}"
        )
        return
    if not 200 <= status < 300 and status not in probe.denied and not probe.known:
        report.findings.append(
            f"{c.variant} {c.key}: A mit B-IDs -> {status}, erwartet {sorted(probe.denied)} "
            f"{response.text[:200]}"
        )
        return
    assert g is not None
    ghost_status = _send(client, g, a).status_code
    if ghost_status != status and not probe.oracle_exempt:
        if probe.known:
            report.known_seen.add(c.key)
            return
        report.findings.append(
            f"{c.variant} {c.key}: Existenz-Orakel — B-IDs -> {status}, unbekannte "
            f"IDs -> {ghost_status} {response.text[:160]}"
        )


def run_isolation(client: TestClient, a: Tenant, b: Tenant, ghost: Tenant) -> Report:
    """Alle Proben als A, dann der Fingerabdruck, dann die Gegenprobe als B."""
    report = Report()
    # Hier statt beim Aufrufer: auch test_org_transfer.py faehrt diesen Lauf.
    _confirm_accounts(a, b)
    _own_invitations(ghost, a, b)
    _memory_extras(ghost, a, b)
    before = fingerprint(b)
    plan: list[tuple[Call, Call | None, Call | None]] = []
    for key, probe in PROBES.items():
        mirror = build_calls(key, probe, b, b)
        phantom = build_calls(key, probe, a, ghost)
        for c in build_calls(key, probe, a, b):
            control = next((m for m in mirror if m.variant == c.variant), None)
            g = next((m for m in phantom if m.variant == c.variant), None)
            plan.append((c, g, control if c.variant != "V3" else None))

    for c, g, _ in plan:
        _probe_as_a(client, report, c, g, a, b)

    after = fingerprint(b)
    changed = sorted(k for k in before if before[k] != after.get(k))
    if changed:
        report.findings.append(f"Schreibzugriff bei B durch A-Aufrufe: {changed}")

    order = {key: i for i, key in enumerate(_DELETE_LAST)}
    controls = sorted(
        (ctl for _, _, ctl in plan if ctl is not None),
        key=lambda ctl: (ctl.method == "DELETE", order.get(ctl.key, -1)),
    )
    seen: set[str] = set()
    for ctl in controls:
        ident = ctl.method + ctl.url + json.dumps(ctl.body) + json.dumps(ctl.query)
        if ident in seen:
            continue
        seen.add(ident)
        response = _send(client, ctl, b)
        report.count("control")
        if control_passes(response.status_code):
            continue
        if PROBES[ctl.key].known:
            report.known_seen.add(ctl.key)
            continue
        report.findings.append(
            f"Gegenprobe {ctl.variant} {ctl.key}: B mit eigenen IDs -> "
            f"{response.status_code} {response.text[:200]}"
        )

    for key, probe in PROBES.items():
        if probe.known and key not in report.known_seen:
            report.findings.append(
                f"{key}: als bekannt markierte Abweichung tritt nicht mehr auf — "
                f"`known` entfernen ({probe.known})"
            )
    return report

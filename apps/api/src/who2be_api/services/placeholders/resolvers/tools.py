"""Tools-Overview-Resolver: kuratierte MCP-Tool-Liste, pro-Agent gefiltert."""

from __future__ import annotations

import asyncpg
from pydantic import BaseModel

from who2be_api.services.placeholders._core import RenderContext, ResolveResult
from who2be_models import AgentCapability, AgentToolPolicy, ReadScope


class ToolsOverviewResolver:
    """Expandiert zu einer Markdown-Liste der fuer DIESEN Agenten verfuegbaren MCP-Tools.

    Inhalt ist kuratiert (DE) — der MCP-Server koennte seine Tool-Liste zwar
    introspectieren (`mcp.list_tools()`), aber die docstrings sind Englisch und
    nicht domaen-freundlich. Hier pflegen wir die Hinweise, die der LLM braucht,
    um die Werkzeuge zur richtigen Zeit zu nutzen. Erweitern: neuer Eintrag in
    `_TOOLS`.

    Pro-Agent-Filter (`ctx.tool_policy`): Es werden nur die Tools gelistet, die
    der Agent laut seiner Policy nutzen darf — Reads gemaess Scope
    (`none` blendet aus, `assigned` ergaenzt einen Hinweis), Writes gemaess
    Capability-Gruppe. Ist keine Policy gesetzt (`None`, z. B. Persona-Body),
    werden nur die Read-Tools gezeigt (Verhalten vor dem Feature).

    `target_id` bleibt ungenutzt. Nie Miss.
    """

    async def resolve(
        self,
        target_id: str,  # noqa: ARG002
        ctx: RenderContext,
        db: asyncpg.Connection,  # noqa: ARG002
    ) -> ResolveResult:
        policy = ctx.tool_policy
        lines = ["## Verfuegbare Werkzeuge", ""]
        any_write = False
        for tool in _TOOLS:
            if not tool.is_visible(policy):
                continue
            if tool.capabilities:
                any_write = True
            suffix = tool.scope_suffix(policy)
            lines.append(f"- **{tool.signature}** — {tool.description}{suffix}")
        lines.append("")
        lines.append(_TOOLS_APPLIED_NOTE)
        if any_write:
            lines.append("")
            lines.append(_TOOLS_WRITE_NOTE)
        return ResolveResult(text="\n".join(lines))


class _ToolDoc(BaseModel):
    """Ein Tool-Eintrag fuer den `tools-overview`-Block.

    Genau eines greift fuer die Sichtbarkeit:
    - `read_domain` (Read-Tool): ``"playbook"``/``"resource"`` (Scope-gefiltert)
      oder ``"persona"``/``"agent"`` (An/Aus-Flag).
    - `capabilities` (Write-Tool): nicht leer ⇒ sichtbar, sobald die Policy EINE
      davon gewaehrt.
    Read-Tools sind ohne Policy (None) sichtbar, Write-Tools nicht.
    """

    signature: str
    description: str
    read_domain: str | None = None
    capabilities: tuple[AgentCapability, ...] = ()

    def is_visible(self, policy: AgentToolPolicy | None) -> bool:
        if policy is None:
            # Vor dem Pro-Agent-Feature gab es nur Read-Tools — Verhalten halten.
            return self.read_domain is not None
        if self.capabilities:
            return any(policy.allows(cap) for cap in self.capabilities)
        if self.read_domain == "playbook":
            return policy.playbook_read != ReadScope.none
        if self.read_domain == "resource":
            return policy.resource_read != ReadScope.none
        if self.read_domain == "persona":
            return policy.persona_read
        if self.read_domain == "agent":
            return policy.agent_read != ReadScope.none
        return True

    def scope_suffix(self, policy: AgentToolPolicy | None) -> str:
        """Hinweis „(nur zugewiesene…)" bei Read-Scope `assigned`."""
        if policy is None:
            return ""
        if self.read_domain == "playbook" and policy.playbook_read == ReadScope.assigned:
            return " — **nur die dir zugewiesenen Playbooks**."
        if self.read_domain == "resource" and policy.resource_read == ReadScope.assigned:
            return " — **nur die dir zugewiesenen Resources**."
        if self.read_domain == "agent" and policy.agent_read == ReadScope.assigned:
            return " — **nur dein eigener Agent**."
        return ""


_TOOLS: list[_ToolDoc] = [
    _ToolDoc(
        signature="get_persona(identifier)",
        read_domain="persona",
        description=(
            "Laedt deine eigene Persona inkl. Profil und verknuepfter Playbooks. "
            "Ruf das einmal zu Beginn auf, wenn du deinen Kontext brauchst. "
            "Pruefe `content.modes`: Wenn die Persona Modi enthaelt, waehle anhand "
            "des Modus-Triggers den passenden Modus und wende dessen "
            "`identity_add` + `output_style_override` an; ohne Trigger-Match "
            "gilt der Default-Modus."
        ),
    ),
    _ToolDoc(
        signature="list_triggers()",
        read_domain="playbook",
        description=(
            "Tabelle aller Trigger-Keywords mit dem zugehoerigen Playbook. "
            "Nutze das, um zu erkennen, ob fuer die User-Frage ein Playbook "
            "vorgesehen ist — bevor du list_playbooks oder fetch_playbook rufst. "
            "Hinweis: fest eingebettete (applied) Playbooks sind bereits im "
            "System-Prompt enthalten und erscheinen hier typischerweise nicht."
        ),
    ),
    _ToolDoc(
        signature="list_playbooks(tag?, trigger?)",
        read_domain="playbook",
        description=(
            "Katalog der Playbooks im Workspace, optional gefiltert nach Tag "
            "oder Trigger. Antwortet mit Name, Beschreibung, Tags, Triggern."
        ),
    ),
    _ToolDoc(
        signature="fetch_playbook(playbook_id)",
        read_domain="playbook",
        description=(
            "Vollstaendiger Body eines Playbooks (Schritte, Anweisungen). "
            "Folge den dort beschriebenen Schritten. "
            "Ist das Playbook ein Composite (Feld `composed_playbooks` nicht leer), "
            "enthaelt die Antwort eine nummerierte Sub-Playbook-Sequenz — "
            "arbeite diese der Reihe nach ab; einzelne Kinder koennen via "
            "erneutem fetch_playbook(child_id) vertieft werden."
        ),
    ),
    _ToolDoc(
        signature="list_resources(tag?)",
        read_domain="resource",
        description=(
            "Katalog der Resources im Workspace (Knowledge-Base-Dokumente), "
            "optional nach Tag gefiltert. Rufe das, wenn ein Playbook auf "
            "Resources verweist oder der User nach Hintergrundwissen fragt."
        ),
    ),
    _ToolDoc(
        signature="fetch_resource(resource_id, block_ids?)",
        read_domain="resource",
        description=(
            "Body einer Resource — optional gezielt einzelne Bloecke "
            "(z. B. ein einzelner Abschnitt)."
        ),
    ),
    _ToolDoc(
        signature="list_agents()",
        read_domain="agent",
        description=(
            "Katalog der Agenten im Workspace (Konfig/Metadaten: Name, Status, "
            "Persona, Template, Policy) — inklusive deaktivierter und gerade erst "
            "angelegter. Nutze das, um bestehende Agenten zu finden, bevor du "
            "einen davon mit get_agent im Detail liest."
        ),
    ),
    _ToolDoc(
        signature="get_agent(agent_id)",
        read_domain="agent",
        description=(
            "Konfig eines Agenten anhand seiner UUID (Persona, Template, Status, "
            "tool_policy, missing/activatable) — kein gerenderter Prompt. Der "
            "richtige Read direkt nach dem Anlegen oder Kopieren und vor dem Editieren."
        ),
    ),
    _ToolDoc(
        signature="fetch_agent(agent_id)",
        read_domain="agent",
        description=(
            "Laedt einen Agenten samt Persona und fertig expandiertem "
            "System-Prompt. Nur fuer DEINEN eigenen Agenten (fremde UUID => nicht "
            "gefunden) — die Konfiguration anderer Agenten liest du mit get_agent."
        ),
    ),
    # --- Schreib-Tools (nur sichtbar, wenn die Policy die Capability gewaehrt) ---
    _ToolDoc(
        signature="create_persona(...) / update_persona(...) / restore_persona(...)",
        capabilities=(AgentCapability.persona_write,),
        description="Personas anlegen, als neuen Draft aendern oder eine Version wiederherstellen.",
    ),
    _ToolDoc(
        signature="set_persona_playbooks(persona_id, playbook_ids)",
        capabilities=(AgentCapability.persona_write,),
        description="Die einer Persona zugeordneten Playbooks setzen (Replace-Semantik).",
    ),
    _ToolDoc(
        signature="create_playbook(...) / update_playbook(...) / restore_playbook(...)",
        capabilities=(AgentCapability.playbook_write,),
        description="Playbooks anlegen, als neuen Draft aendern oder wiederherstellen.",
    ),
    _ToolDoc(
        signature="set_playbook_resource_links(...) / set_playbook_composes(...)",
        capabilities=(AgentCapability.playbook_write,),
        description=(
            "Resource-Verweise bzw. die Sub-Playbook-Sequenz eines Composite-"
            "Playbooks setzen (Replace-Semantik)."
        ),
    ),
    _ToolDoc(
        signature="create_resource(...) / update_resource(...) / restore_resource(...)",
        capabilities=(AgentCapability.resource_write,),
        description="Resources anlegen, als neuen Draft aendern oder wiederherstellen.",
    ),
    _ToolDoc(
        signature="set_resource_sub_resources(resource_id, links)",
        capabilities=(AgentCapability.resource_write,),
        description="Die Sub-Resources einer Resource setzen (Replace-Semantik).",
    ),
    _ToolDoc(
        signature="create_agent(...) / update_agent(...) / copy_agent(...)",
        capabilities=(AgentCapability.agent_write,),
        description="Agenten anlegen, aendern oder duplizieren.",
    ),
    _ToolDoc(
        signature="transition_persona/playbook/resource(id, version, to, note?)",
        capabilities=(
            AgentCapability.promote_retire,
            AgentCapability.persona_write,
            AgentCapability.playbook_write,
            AgentCapability.resource_write,
        ),
        description=(
            "Eine Version in einen neuen Status schalten. Nach `draft`/`review` "
            "genuegt die jeweilige Schreib-Capability; nach `active`/`inactive` "
            "(veroeffentlichen/zurueckziehen) ist die Capability `promote_retire` noetig."
        ),
    ),
]

# Applied-vs-Triggered-Hinweis: Fest im System-Prompt eingebettete Playbooks
# (Pill / applied) gelten immer und sind bereits expandiert — kein MCP-Call noetig.
# Triggered Playbooks werden via list_triggers() entdeckt und nur bei
# Trigger-Match via fetch_playbook() geladen.
_TOOLS_APPLIED_NOTE = (
    "**Invocation-Wege:** Fest eingebettete Playbooks (applied, bereits im "
    "System-Prompt) gelten immer. Weitere Playbooks nur bei Trigger-Match laden "
    "— erst list_triggers(), dann fetch_playbook(id)."
)

# Erscheint nur, wenn dem Agenten mindestens ein Schreib-Tool freigeschaltet ist.
_TOOLS_WRITE_NOTE = (
    "**Schreibzugriff:** Die oben gelisteten Schreib-Tools sind fuer dich "
    "freigeschaltet. Tools, die hier nicht stehen, sind fuer diesen Agenten "
    "gesperrt und werden serverseitig abgelehnt — versuche sie nicht."
)

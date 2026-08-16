# PROJECT — Wohin (Ziel-Anker)

**Mission:** Who2Be ist eine selbst-gehostete AgentDB für **versionierte Persona-
und Playbook-Verwaltung** — eine zentrale, versionierte Quelle der Wahrheit für
Agent-Persona, Playbooks, Resources und Composites, abrufbar per REST-API und MCP.

**Outcome:** Teams pflegen Personae/Playbooks/Resources versioniert (draft →
review → active → inactive), nutzen sie über MCP in beliebigen LLM-Clients und
verwalten Zugriff mandantenfähig (Org → Workspace → Rollen).

**Zweite Achse — WorkArea + Knowledge Base (ADR-0047/0048/0049):** Neben der
*kuratierten*, versionierten Achse (Persona/Playbook/Resource — was ein Agent
sein und tun soll) gibt es die *arbeitende*, unversionierte Achse: die WorkArea
als Ablage für Material, das ein Agent im Lauf sammelt (Dokumente, Dateien,
Tabellen), und die Knowledge Base als belegpflichtige Verdichtung daraus
(jede Aussage trägt ihren Beleg und ihre Sicherheitsstufe). Beide sind
**Kontext-Speicher für Agenten** — Mission unverändert, Scope präzisiert.

## Non-Goals (stoppt Scope-Drift)

- **Kein** allgemeines CMS / Wiki — der Fokus ist Agent-Persona/Playbook/Resource.
  *Gilt ausdrücklich auch für WorkArea/KB:* die WorkArea ist der Arbeitsspeicher
  eines Agenten, kein Dokumenten-Management und kein Team-Wiki; die KB ist ein
  Belegnetz für Agenten-Aussagen, keine Redaktions- oder Publikationsoberfläche.
  Was menschlich kuratiert und veröffentlicht wird, gehört auf die
  Resource-Achse.
- **Kein** Chat-/Agent-Runtime-Host — Who2Be *speichert und liefert* Kontext, es
  *führt* keine Agents aus. *Auch mit WorkArea/KB unverändert:* die App ruft kein
  Modell auf. Sie kennt das Modell eines Agenten nur als **Konfigurationsangabe**
  (gepflegt von Menschen, nicht von Agenten) und protokolliert sie im
  Zugriffslog — daraus folgt keine Laufzeit-Kontrolle über den Modellaufruf.
- **Kein** Analyse-/BI-Werkzeug — der Tabellen-Store beantwortet Agenten-Fragen
  über abgelegtes Material (read-only SQL, Aggregate); er ist kein Data
  Warehouse und rendert bewusst keine Charts.
- **Kein** Vendor-Lock-in auf eine LLM — MCP-first, modellneutral.
- **Kein** Verzicht auf die On-Prem-Edition zugunsten Cloud — eine Codebase, zwei
  Build-Profile (ADR-0028/0029); Billing ist build-isoliert.

## Pointer

- Einstieg: [`../../README.md`](../../README.md), [`../../AGENTS.md`](../../AGENTS.md)
- WAS/WARUM des aktiven Vorhabens: [`../../.github/PROJECT.md`](../../.github/PROJECT.md)
  (Outcome, Why, Acceptance Criteria, Constraints, Out of Scope)
- Architektur-Blueprint: [`../../docs/architecture.md`](../../docs/architecture.md)
- Aktueller Stand: [`STATE.md`](STATE.md)

_Snapshot: 2026-08-16 (WorkArea/KB-Rahmung ergänzt). Update nur bei Ziel-Änderung._

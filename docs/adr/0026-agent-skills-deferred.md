# ADR-0026 — Persona-„Skills": deskriptives Feld deaktiviert (Coming Soon)

- Status: Akzeptiert — deskriptives Feld deaktiviert (Coming Soon)
- Datum: 2026-06-04
- Kontext: Who2Be — Persona-Aggregat, Brainstorm „Machen Skills Sinn?"
- Bezug: ADR-0009 (jsonb-Schema-Evolution), ADR-0024 (Composite-Playbooks),
  ADR-0005 (MCP als HTTP-Client), ADR-0012 (MCP-Write-Tools deferred)

## Kontext

Das Persona-Aggregat trägt seit „Gap 3.5" ein Feld `skills:
list[SkillRef]` (`packages/models/src/who2be_models/persona.py`). Ein
`SkillRef` ist **rein deskriptiv**:

```python
class SkillRef(BaseModel):
    name: SkillNameStr      # 1..100 Zeichen
    note: str = ""          # 0..1000 Zeichen, Relevanz-Hinweis
```

Wirkung im Lauf: `render_skills_table`
(`apps/api/src/who2be_api/services/placeholders/registry.py`) hängt beim
`get_persona`-Render eine Markdown-Tabelle **„## Skills | Skill | Hinweis"**
an den Profil-Body. Der Agent erhält also nur einen Hinweistext, welche
Skills „relevant" sind — **keine Ausführungs-Bindung, kein Fetch, keine
Verknüpfung** zu einem anderen Aggregat. Frontend-Oberfläche:
`PersonaSkillsEditor` (Formular) und `PersonaSkillsTable` (read-only
Detail-Page).

Damit sitzt das Feature in einem konzeptionellen Niemandsland:

1. **Zu vage zum Ausführen.** Anders als Playbooks/Resources (echte
   Slash-Refs / Katalog-Pills mit `fetch_playbook`/`fetch_resource`)
   referenziert ein Skill nichts — der Agent kann damit nichts „tun".
2. **Redundant zum Beschreiben.** Ein deskriptiver Fähigkeits-Hinweis ist
   faktisch dasselbe wie ein **Trait**, ein **Tag** oder ein Satz im
   Persona-Body — drei Wege fürs gleiche Ziel, gegen das Prinzip
   „Single-Source pro Entscheidung".
3. **Überlappung mit Vorhandenem.** Soll ein Skill *handlungsleitend* sein,
   ist das exakt die Rolle von **Playbooks** — und Persona-**Modi** binden
   bereits ein `playbook_id`. Skills doppeln das halbgar.

Gleichzeitig wird „Skill" in der Agenten-Welt zu einem echten Primitive
(Agent Skills = `SKILL.md` + gebündelte Dateien, on-demand geladen,
versioniert). Für eine selbstgehostete „AgentDB" wäre **das** ein echtes,
differenzierendes Feature — hat mit dem heutigen `name+note`-Textfeld aber
nur den Namen gemein.

## Optionen

- **A — Status quo lassen.** Deskriptives `SkillRef`-Feld bleibt aktiv.
  Null Aufwand, aber das Feld trägt seinen Platz nicht (siehe 1–3) und
  zementiert die Redundanz zu Traits/Tags/Playbooks.
- **B — Deskriptives Skills-Feld deaktivieren.** UI verstecken
  (`PersonaSkillsEditor`/`PersonaSkillsTable`), `render_skills_table` nicht
  mehr anhängen. Modell-Feld `skills` bleibt mit Default `[]` als
  Wire-/jsonb-Backward-Compat erhalten (ADR-0009) — kein Datenverlust,
  voll reversibel. Kleiner, sauberer Schnitt; der `get_persona`-Output
  verliert nur die Skills-Tabelle.
- **C — Echte, hochladbare Agent-Skills bauen.** Skill wird ein eigenes,
  versioniertes Aggregat (analog Resource/Playbook): `SKILL.md` +
  optionale Bundle-Dateien, workspace-aware, Status pro Version (ADR-0020),
  per MCP on-demand ladbar. Großes, eigenes Feature — würde aber sauber ins
  Versionierungs-/Workspace-Modell passen und das deskriptive Feld
  vollständig ersetzen.

## Entscheidung

**B (deaktivieren) als Brücke zu C (echte Agent-Skills).** Das deskriptive
`SkillRef`-Feld wird vorläufig **deaktiviert und als „Coming Soon"
dargestellt** — sichtbar, aber nicht nutzbar. Begründung: Das heutige
`name+note`-Feld trägt seinen Platz nicht (siehe 1–3), aber „Skill" soll als
Konzept erhalten bleiben und später als echtes, versioniertes Agent-Skill-
Aggregat (Option C) zurückkommen. Statt es ersatzlos zu entfernen,
kommunizieren wir es als geplantes Feature.

Umsetzung (reversibel, kein Datenverlust):

- **Backend-Flag** `SKILLS_ENABLED = False`
  (`apps/api/.../placeholders/registry.py`) gated beide Render-Pfade:
  `render_skills_table` liefert `""`, die Skills-Sektion in
  `_render_persona_profile` wird übersprungen. Reaktivierung = Flag auf
  `True`.
- **MCP** (`get_persona`/`PersonaWithPlaybooks`): Skills sind im
  dokumentierten Tool-Vertrag als „Coming Soon, derzeit deaktiviert"
  ausgewiesen und erscheinen nicht im `body_rendered`.
- **Frontend**: `PersonaSkillsEditor`/`PersonaSkillsTable` sind durch den
  `SkillsComingSoon`-Platzhalter ersetzt (Editor-Formular + Detail-Page).
  Die Komponenten bleiben im Repo für die Reaktivierung.
- **Datenmodell** unverändert: `skills` bleibt mit Default `[]` (ADR-0009),
  der Form-Passthrough erhält bestehende Inhalte verlustfrei.

Leitplanke: **kein Ausbau** des deskriptiven Felds (keine neuen
Render-Pfade, keine Skill→X-Verknüpfungen) — der nächste Schritt ist
Option C, nicht das Reaktivieren des Freitext-Felds.

## Re-Evaluation-Trigger

Diese Entscheidung ist zu treffen, wenn:

1. **Nutzer-Signal** zeigt, ob Skills überhaupt gepflegt werden — wird das
   Feld real genutzt, ist B teurer; bleibt es leer, ist B trivial.
2. **Agent-Skill-Use-Case** konkret wird (Agent soll eine paketierte
   Fähigkeit on-demand laden) → Option C mit eigener Design-ADR
   (Aggregat-Schema, Bundle-Storage, MCP-Tool `fetch_skill`,
   Versionsstatus, Security-Review des Lade-Pfads analog ADR-0012).
3. **Nächster Persona-Editor-Pass** ohnehin ansteht → günstiger Moment für
   B (UI + Render still legen), ohne separaten Eingriff.

Bei C: neue ADR; diese ADR (0026) wird auf „Superseded" gesetzt. Bei B:
diese ADR auf „Akzeptiert (Deaktiviert)" mit Verweis auf den Deaktivierungs-
PR.

## Konsequenzen

- `packages/models/.../persona.py` (`SkillRef`, `skills`-Feld) bleibt
  unverändert — nur das *Rendering* ist hinter `SKILLS_ENABLED` deaktiviert.
- Reaktivierung ist ein Einzeiler (`SKILLS_ENABLED = True`) plus das
  Wiedereinhängen von `PersonaSkillsEditor`/`PersonaSkillsTable` — die
  Komponenten und ihre Tests bleiben erhalten. Das Render-Verhalten ist
  weiterhin getestet (Flag-gegated in `test_placeholder_renderer.py` /
  `test_persona_service.py`).
- Pull-Requests, die das deskriptive Skills-Feld *ausbauen*, sind gegen
  diese ADR prüfbar (Leitplanke „kein Ausbau").
- Das `skills`-jsonb-Feld bleibt durch ADR-0009 additiv evolvierbar — die
  Deaktivierung wie eine spätere Migration zu C bricht keine Bestands-
  Snapshots.

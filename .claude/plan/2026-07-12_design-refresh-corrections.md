# Design-Refresh — Nachbesserungen (User-Review)

**Branch:** `claude/code-agent-setup-lmpt8u` (frisch von `origin/main` nach Merge #309).
Quelle: hochgeladene Mockups (`scratchpad/design_upload/*.dc.html`).

## Zu beheben (aus User-Feedback)

1. **Dashboard** — Feedback-Bereich (`FeedbackTiles`) am Seitenende ENTFERNEN
   (Mockup endet mit dem Aktivitäts-Feed, kein Feedback-Block).

2. **Agents-Übersicht** — fehlt:
   - Filter-Toolbar + Suchfeld (Segment-Tabs Alle/Aktiv/Deaktiviert/Unvollständig
     + Suche + Filter).
   - Meta-Pills je Karte: Persona, System-Prompt/Template · v{n}, N Playbooks
     (bei unvollständig: „Persona fehlt" destructive).

3. **Agent-Details:**
   - „Zusammensetzung" stärker am Mockup orientieren (System-Prompt-Zeile,
     Persona-Zeile, verknüpfte Playbooks als Chips/Zeilen).
   - Tab **Werkzeuge**: Persona-/Playbook-/Resource-Tags als **Pills mit
     Dropdown + Suchfeld** (vorhandene finden ODER neu erstellen) — analog zu
     den übrigen Tag-Feldern (`TagInput`).
   - Tab **Verbindung**: nicht alle Tokens flach zeigen — aktive Tokens sichtbar,
     abgelaufene/widerrufene hinter „N abgelaufene · widerrufene" einklappen
     (Mockup-Verhalten).

4. **Persona-Übersicht** — fehlen Meta-Pills: N Modi, N Playbooks,
   „Verwendet von N Agents" / „Kein Agent". (Filter-Toolbar prüfen.)

5. **Persona-Details:**
   - **Modi** als EIGENER Tab (Bearbeiten / Modi / Playbooks / Versionen).
   - **Playbooks**-Tab: optimierte Darstellung (View/Edit-Toggle, Zeilen mit
     Status + „Kategorie · N Trigger", Composite-Aufklapp für Sub-Playbooks).

6. **Andere Übersichten prüfen** — fehlende neue Elemente/Re-Designs bei
   System-Prompts, Resources, Feedback (nur was OHNE Backend-Änderung geht;
   Datenlücken dokumentieren statt erfinden).

## Regeln
- Geteilte Komponenten wiederverwenden (EntityCard/MetaPill/Tabs/TagInput/
  ListFilterBar). Keine Duplikate. Volle Umlaute. Keine neuen Tokens/#hex/px.
- Kein Erfinden von Daten: fehlt ein Feld im List-Endpoint → Pill weglassen und
  im Report vermerken (ggf. Nachtrag).
- DoD: `npm run lint && npx tsc --noEmit && npm run test:coverage && npm run build`
  grün, dann Commit + Push + NEUE Draft-PR.

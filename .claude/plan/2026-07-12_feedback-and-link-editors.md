# Runde 3 — Link-Editoren + zentrales Feedback + Einzel-Feedback-Detail

Branch: `claude/code-agent-setup-lmpt8u` (frisch von main nach Merge #310).
Quelle: Mockups (`scratchpad/design_upload/*.dc.html`) + User-Review.

## WP1 — Persona: Playbook-Verknüpfungen bearbeiten (Edit-Modus)
Edit-Modus an das Mockup (`Persona-Detail.dc.html`, `pbEditing`) angleichen:
- Hinweisbox: „Aus Editor-Text" verlinkte Playbooks sind editor-verwaltet, hier
  nicht entfernbar.
- **Verknüpft**-Liste: editor-verlinkte mit Marker (managed), manuelle mit
  „Entfernen".
- **Playbook hinzufügen**: Suchfeld + Liste verfügbarer Playbooks je „Verknüpfen"
  (statt des heutigen Checkbox-Batch-Pickers). Leerzustand „Kein passendes …".

## WP2 — Feedback zentralisieren (nicht doppelt im Detail)
Eingebettetes `FeedbackPanel` aus **Resource-Detail** (und für Konsistenz
**Persona-Detail**) entfernen. Feedback bleibt zentral im Feedback-Bereich; der
„Feedback"-Header-Button verlinkt bereits dorthin. (Kein doppeltes „unten drunter".)

## WP3 — Resource: Sub-Resources-Verwaltung (Tab)
Analog WP1 an das Mockup (`Resource-Detail.dc.html`, Sub-Resources-Tab):
- Hinweis „Im Text (Block #N)" = editor-eingebettet, hier nicht entfernbar.
- **Eingebunden**-Liste: manuelle mit Lazy/Inline-Umschalter + Entfernen.
- **Sub-Resource hinzufügen**: Suchfeld + Liste je „Hinzufügen". Einfaches
  Hinzufügen/Verwalten/Sehen.

## WP4 — Einzel-Feedback-Detailseite (NEU, über die Mockups hinaus)
Neue Ebene: aus dem Posteingang auf EIN Feedback klicken → Detailseite dieses
einen Feedback-Eintrags:
- Worauf es sich bezieht (Element + Link), Signal, Notiz, Quelle (Agent/Mensch),
  Version, erstellt/zuletzt bearbeitet, aktueller Status.
- Bearbeiten/Planen/Handeln: Resolution setzen (`ResolutionSegments`), Notiz,
  löschen. Route z. B. `/feedback/item/:feedbackId`.
- Datenverfügbarkeit prüfen (GET-by-id? `resolved_at`/Historie?) — fehlt etwas,
  minimal Backend ergänzen; nichts erfinden.

## Regeln
Geteilte Komponenten wiederverwenden (DetailHeader, Card, StatusBadge, MetaPill,
ResolutionSegments, EntityIcon). Volle Umlaute, keine neuen Tokens. DoD grün,
dann Commit + Push + neue Draft-PR.

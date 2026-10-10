# Navigation W2-a1: Agent-Seite mit Tabs (Umbau ohne neuen Inhalt)

Karte: t_6e48b9ac · Spec: navigation-transparenz-design-2026-10 §3.1 · Owner A2a/A3a

## Outcome

`/w/:ws/agents/:id` zeigt unter dem unveränderten Kopf eine Tab-Leiste
Überblick · Gedächtnis · Prüffälle · Einstellungen; `?tab=` ist die einzige Quelle.

## Schnitt (PM-Entscheidung im Kartenkommentar)

- W2-a1 (diese Karte): Tabs, `?tab=`, Anker-Umleitung, Platzhalter
  „Weiterentwicklung“ hinter Modulkonstante (aus).
- W2-a2 (t_3b72bed0): Klapp-Regel t_42bff43b aus AgentHierarchyView entfernen.
  Bis dahin klappt die Zusammensetzung unter md weiter, jetzt im Tab Überblick.

## Entscheidungen

- Tabs = vorhandene Primitive `components/ui/tabs` (bricht um nach Mobil-Spec M7,
  kein Scroll/Fade — die Spec-Zeile „horizontal scrollbar mit Fade“ ist durch
  M7/W1=a überholt). Zustand über `useVersionDeepLink` (wie Persona/Resource).
- Gedächtnis-Tab nur ab editor (die Karte rendert für viewer nichts);
  `?tab=memory` fällt für viewer auf den Überblick.
- Anker: `#tests` → `?tab=tests`; `#memory` → `?tab=memory#memory` (Hervorhebung
  bleibt); `#sessions` → Überblick, solange Weiterentwicklung aus ist, sonst
  `?tab=evolution`; `#delegations` → Überblick mit Hash. Expliziter `?tab=` gewinnt.
- Keine Zähler am Tab (wäre neuer Inhalt, kommt mit W2-b/W3).
- `AgentMemoryCard` bekommt `framed` (Default true, Tab: false).
- e2e scroll-guard M7: Agent hat jetzt zwei Leisten; Probe prüft beide
  (Seite 4 Tabs, Einstellungen-innere 3 Tabs).

## Verifikation

- `npm run lint`, `tsc -b`, `npm run i18n:check`, `npm run test:coverage`
- e2e Projekt mobile (scroll-guard) lokal soweit Stack verfügbar, sonst CI.
- Fotos 1280/390 hell/dunkel, measure.json.

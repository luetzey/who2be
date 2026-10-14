# E5j — „Zu erledigen“: Nachkontroll-Zeilen, Überblick-Kachel → Tab

Karte t_3be62dd2 · Basis origin/main 2b9c05d5 · Spec phase-e-web-neuschnitt-2026-10.md §5, §7.1

## Completion-Condition
- Abschnitt „Nachkontrollen fällig“ zeigt Zeilen aus `listSessions({due:true, agent_id?}, {limit:5})`,
  je Review eine Zeile: „Review vom {date} · {agent}“, Pill „seit n Tagen fällig“/„heute fällig“,
  Meta „{due_measure_count} Änderungen zur Nachkontrolle · Termin {date}“,
  Aktion `default` „Nachkontrolle öffnen“ → `/agents/:agentId/reviews/:sid?change=first-due`.
- Abschnittszahl bleibt `follow_ups_due` (Server); Meta-Zahl = `due_measure_count` (Server); Web filtert/rechnet „fällig“ nicht nach.
- „Weitere laden“ (Cursor), gesperrt während des Ladens (kein Doppel-Request); mit `?agent=` zusätzlich „Bei {agent} ansehen →“ auf `?tab=evolution`.
- viewer: kein `/feedback-sessions`-Request. Fehler der Liste: nur Abschnittsfehler.
- Key `inbox.followUps.pending` entfällt (de/en).
- Agent-Überblick: Kachel „Rückmeldungen offen“ → `?tab=evolution`.

## Dateien (8)
InboxPage.tsx, InboxPage.test.tsx, InboxPage.a11y.test.tsx, AgentOverview.tsx, AgentOverview.test.tsx, de.json, en.json, changelog.d Fragment.
`InboxSection.tsx` bleibt unverändert (Budget): „Weitere laden“/Agent-Link stehen unter dem Abschnitt.

## Verifikation
`npx tsc -b`, vitest (inbox, agents), lint, e2e-mobile, Fotos 1280/390 hell/dunkel editor+viewer + measure.json.

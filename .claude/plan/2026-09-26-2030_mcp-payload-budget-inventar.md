# MCP-Payload-Budget: Inventar, Obergrenze, Regressionsschutz

Karte `t_89ffc946`. Eltern-Karte `t_4ce1b187` (PR #666) hat den `format="text"`-
Pfad fuer `fetch_playbook` eingefuehrt; diese Karte misst den **Rest** der
Werkzeuge gegen dieselbe Schwelle und haelt das Budget als Regel fest.

## Messmethode

Gemessen wurde die **serialisierte Antwort, wie sie beim Agenten ankommt** —
nicht die REST-Antwort und nicht geschaetzt. Jeder Aufruf lief live gegen den
Produktions-MCP (`mcp.luetzenburg-cloud.de`) mit dem groessten vorhandenen
Objekt je Typ (Persona `Coder`, Playbook `Code-Task-Flow`, Resource
`Dokumentations-Standards` mit 92 Bloecken, Agent `Coder`). Die Zahl ist die
Zeichenlaenge der Tool-Antwort; ueber 50 000 Zeichen legt die Laufzeit die
Antwort in eine Spillover-Datei statt sie dem Modell zu zeigen.

Die Schwelle 50 000 ist keine Who2Be-Einstellung, sondern die Vorgabe der
Laufzeit des Konsumenten. Sie ist damit nicht verhandelbar, sondern eine
Randbedingung.

## Inventar

**Die maßgebliche Inventar-Tabelle steht in
[`docs/mcp-payload-budget.md`](../../docs/mcp-payload-budget.md)** — dort wird
sie gepflegt. Dieser Plan hielt zwischenzeitlich eigene Zahlen; zwei davon
(`list_external_tools`, `search(limit=50)`) stammten aus einem frueheren,
kleineren Messlauf und wichen von der Doku ab. Eine Messung, eine Quelle: die
Zahlen stehen ab jetzt nur noch im Budget-Dokument, hier steht das Vorgehen.

Kurzfassung des Befunds, gemessen 2026-09-26: ueber der Grenze lagen
`list_playbooks`, `get_persona`, `list_versions`, `fetch_playbook`,
`fetch_agent`, `diff_versions`, `list_system_prompts` und `get_system_prompt`;
`list_resources` liegt mit 786 Zeichen am anderen Ende und ist das Vorbild
(Summary statt Volltext).

## Befund

Jedes Werkzeug ueber der Schwelle reisst sie aus **einem** Grund: es liefert
BlockNote-Editor-JSON mit, das denselben Text ein zweites Mal traegt. Der
Nutztext-Anteil liegt bei `get_persona` bei rund 5 % — der Rest ist `props`,
`styles`, `children` und Block-IDs. Kein Werkzeug reisst die Schwelle, weil
es zu viel Inhalt haette.

## Vorgehen

1. **Obergrenze nachziehen** (Datei: `apps/mcp/src/who2be_mcp/server.py`).
   Derselbe additive `format`-Parameter wie in PR #666, gleiche Semantik, auf
   die vier Werkzeuge ueber der Schwelle ausser `fetch_playbook`:
   `get_persona`, `fetch_agent`, `list_playbooks`, `list_versions`.
   `format="full"` bleibt Default — kein bestehender Konsument verliert etwas;
   `format="text"` laesst das Editor-JSON weg.
2. **Dokumentieren** (`docs/mcp-payload-budget.md`): das Budget als Regel, die
   Begruendung (fremde Laufzeiten schneiden ab, ohne zu melden), die
   Messmethode und das Inventar.
3. **Regressionsschutz** (`apps/mcp/tests/test_tool_payload_budget.py`): je
   Werkzeug ein Test, der die **serialisierte Antwortgroesse** gegen die
   Obergrenze prueft — Verhalten, nicht Feldnamen. Rot-Probe: jedes Fixture
   ist so bemessen, dass der `full`-Pfad die Schwelle tatsaechlich reisst;
   tut er das nicht, faellt der Test mit eigener Meldung. Damit kann der Test
   nicht gruen bleiben, wenn der Text-Pfad wegfaellt.

`fetch_playbook` wird **nicht inhaltlich veraendert** (`t_4ce1b187` / PR #666 hat
den Fall geloest). Bei der Konfliktaufloesung gegen `origin/main` wird es aber
auf die gemeinsame Quelle `_RESPONSE_FORMATS` und `_playbook_without_body`
umgestellt — verhaltensgleich, weil sonst zwei konkurrierende Quellen fuer
denselben Begriff in einer Datei stehen (`AGENTS.md`, Single Source of Truth).

## Runde 2 (nach Review)

Drei Blocker, alle innerhalb des Zuschnitts geloest:

1. **`get_persona(format="text")` griff nur halb.** Die Antwort ist
   `PersonaWithPlaybooks`; geleert wurden nur die Persona-Bloecke, die
   Playbook-Bodies in derselben Antwort blieben. Ab etwa vier verknuepften
   Playbooks reisst die Antwort dadurch weiter — und eine Persona ohne
   Playbooks ist beim Boot-Schritt der Ausnahmefall. Die Rot-Probe traf ins
   Leere, weil alle Fixtures `/playbooks` mit `[]` beantworteten. Jetzt schneidet
   `format="text"` beide Haelften, und ein Test mit fuenf verknuepften Playbooks
   belegt es — sein Fixture ist so gebaut, dass die Persona allein unter der
   Grenze bleibt und erst die Bodies sie reissen (86.448 Zeichen ohne Zuschnitt).
2. **Konflikt gegen `origin/main`** aufgeloest, `fetch_playbook` auf die
   gemeinsame Quelle umgestellt (siehe oben).
3. **Inventar vervollstaendigt.** `list_system_prompts` (50.766),
   `get_system_prompt` (50.441) und `diff_versions` (52.116) reissen gemessen und
   fehlten; `get_version` (49.223) steht als Beobachtungsposten. Keiner der drei
   ist trivial zuschneidbar — bei den System-Prompts verbietet `min_length=1` den
   leeren Body, bei `diff_versions` haengt ein Frontend-Vertrag daran. Sie stehen
   daher mit Messwert und benanntem Weg im Budget-Dokument, nicht halbfertig im
   Code. Zwei neue Guards halten das nachpruefbar statt behauptet.

## Zuschnitt

Fuenf Dateien: `server.py`, `test_tool_payload_budget.py`,
`docs/mcp-payload-budget.md`, ein `changelog.d/`-Fragment, diese Plan-Datei.
Grenze der Karte: acht.

## Nicht in dieser Karte

- Den Default auf `"text"` kippen. Waere die wirksamere Loesung, ist aber ein
  Vertragsbruch fuer bestehende Konsumenten und braucht eine eigene
  Entscheidung.
- `list_external_tools` und `fetch_resource` umbauen. Beide liegen unter der
  Schwelle; `list_external_tools` ist mit ~24 000 Zeichen der naechste
  Kandidat, wenn weitere Bindungen dazukommen — im Budget-Dokument als
  Beobachtungsposten vermerkt.

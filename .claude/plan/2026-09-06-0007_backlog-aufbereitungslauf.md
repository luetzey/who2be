# Backlog-Aufbereitungslauf (2026-09-06)

Playbook: **Issue-Refinement** (`290b0c4f`), Prüfnorm: Resource
**Agent-ready Arbeitspaket** (`73a86231`). Auftrag: jedes offene Issue gegen die
Norm prüfen, Belegbares selbst entscheiden und mit Beleg ins Issue schreiben,
Urteilsfragen als Kommentar mit drei Optionen + Empfehlung zurückgeben, danach
die Warteschlange (#442) neu ordnen und in Wellen gruppieren.

## Ausgangslage

Die Warteschlange in #442 ist seit ihrem letzten Stand (2026-09-05 17:05)
überholt. Sechs der zehn gelisteten Pakete sind gemergt und geschlossen:

| Paket | Stand |
|---|---|
| #429 „Coming soon“-Modus | geschlossen 2026-09-05 20:17 |
| #450 Registry-Pull | geschlossen 2026-09-05 19:46 |
| #451 Kettentest Billing | geschlossen 2026-09-05 20:30 |
| #449 Tarife/Kontingent | geschlossen 2026-09-05 21:25 |
| #452 Webhook-Härtung | geschlossen 2026-09-05 22:15 |
| #438 Responsive-Fundament | geschlossen 2026-09-05 22:49 (Merge `3ddbbc1`) |

Gleichzeitig sind vier Issues neu, die in der Liste **nicht** vorkommen —
allesamt Nebenfunde aus genau diesen Läufen: #458, #462, #463, #465.

Damit ist der Cloud-Launch-Block bis auf #453 abgearbeitet, und die
Owner-Vorgabe „nach dem Cloud-Launch-Block“ ist erschöpft.

## Triage der offenen Issues

Legende: **E** = im Repo belegt, vom Refiner entschieden · **U** = braucht
Urteil, bleibt `needs-decision`.

| Issue | Norm-Stand vorher | Befund | Ergebnis |
|---|---|---|---|
| #465 Animationen tot | Befund, 0 von 4 Pflichtfeldern | **E** | veredelt → `agent-ready`, `size/S` |
| #463 Fünf Restbefunde | Befund, 0 von 4 | **E** (Punkte 2/4/5) + **U** (1/3) | veredelt auf 2/4/5 → `agent-ready`, `size/S`; 1/3 als Out-of-Scope + Entscheidungs-Kommentar |
| #462 Verspätetes Ereignis | Befund, 0 von 4 | **U** | bleibt `needs-decision` — Optionen stehen bereits im Body |
| #458 MINIO_ROOT_PASSWORD | Befund, 0 von 4 | **E** | veredelt → `agent-ready`, `size/S` |
| #453 E2E-Journey Billing | 4 von 4 + 5 Weichen | **U** (CI-Weg A/B/C) | unverändert blockiert |
| #436 Fehlercodes W0 | 4 von 4 | **U** (Vokabular A/B/C) | unverändert blockiert |
| #430 Angemeldet bleiben | vollständig | — | `agent-ready`, unverändert |
| #427 Agent-Favoriten | vollständig | — | `agent-ready`, unverändert |
| #428 #402 #431 #435 | `size/M` | — | nicht in der Queue (Zuschnitt, kein Refinement) |
| #454 #338 | `human-only` | — | Lauf endet dort (Playbook Schritt 1) |

### Die drei selbst entschiedenen Weichen

**#458 — Platzhalter statt Compose-Default.** Das Issue stellt die Frage als
Sicherheitsabwägung dar. Sie ist im Repo bereits beantwortet:

- Vier weitere Pflicht-Secrets derselben Datei tragen `CHANGE_ME_<zweck>`:
  `deploy/hetzner/.env.example:19, 89, 112, 127`.
- Der `:?`-Guard auf `MINIO_ROOT_PASSWORD` ist der **einzige** in der ganzen
  Compose-Datei (`deploy/hetzner/who2be/docker-compose.yml:93`), während
  `MINIO_ROOT_USER` direkt daneben (`:89`) einen Default trägt — die
  Asymmetrie ist gesetzt, nicht vergessen.
- Das Root-`.env.example:124` schreibt sie aus: „MINIO_ROOT_PASSWORD ist
  PFLICHT — ohne Wert […]“.

Ein Compose-Default würde eine dokumentierte Entscheidung zurücknehmen. Das
wäre die begründungspflichtige Richtung; der Platzhalter erhält den Status quo.
Nach Playbook Schritt 4 damit keine offene Weiche, sondern unerledigte
Recherche.

**#465 — Bewegung ja, über Motion-Tokens.** Die Optionen A (Plugin), B (Klassen
entfernen) und C (Tokens) sind im Repo entschieden, weil
`docs/frontend/design-language.md` laut CLAUDE.md verbindlich ist:

- §7.3 listet „Dialog open/close“, „Dropdown open“ und „Toast slide-in“ als
  gesetzte Muster → die Übergänge sind **gewollt**, B fällt weg.
- §7.2 und §12 Nr. 6: „Keine hardcoded `ms`-Werte. Token oder nichts.“ →
  die Dauer/Easing muss aus `--duration-*`/`--ease-*` kommen.
- Die Tokens existieren (`globals.css:128-130, 202-204`), die
  Reduced-Motion-Regel ebenfalls (`:620`).

Offen bleibt damit nur das **Wie** (Plugin mit Token-Duration vs. eigene
Keyframes) — und das ist nach der Norm ausdrücklich das, was der ausführende
Agent selbst herausfindet. Die Akzeptanzkriterien sind deshalb weg-agnostisch
formuliert.

**#463 — Punkte 2/4/5 sind Konvention, nicht Abwägung.**

- Punkt 2: `main.py:309` reicht `settings` bereits an `is_cloud(settings)`
  durch; `include_routers` ruft eine Zeile später selbst `get_settings()`
  (`packages/billing/src/who2be_billing/__init__.py:38`). Die Konvention steht
  direkt daneben.
- Punkt 5: `_coerce_int` existiert (`webhook.py:105`) und wurde laut Kommentar
  bei `:321` genau für dieses Muster eingeführt; `:161` trägt noch
  `value.isdigit()`.
- Punkt 4: der Mollie-Pfad protokolliert bereits (`router.py:262`); die
  Log-Stufen stehen im Issue.

Punkt 1 (404-/400-Orakel) und Punkt 3 (Dedupe-Namensraum) bleiben Urteil und
gehen als Out-of-Scope plus Kommentar zurück.

## Neue Reihenfolge

Kriterien unverändert: harte Abhängigkeit → Owner-Vorgabe → Fundament vor
Fläche → Inventar vor Zuschnitt → bei Gleichstand das kleinere.

1. **#458** — Deploy-Vorlage. Blockiert #454 belegbar: alle drei
   Overlay-Kombinationen brechen ohne `MINIO_ROOT_PASSWORD` ab (nachgeprüft).
   Kriterium 1 vor allem anderen; zugleich das kleinste Paket der Liste.
2. **#463** — Restbefunde 2/4/5. Owner-Vorgabe (Cloud-Block), letztes
   Code-Paket des Blocks; blockiert selbst nichts.
3. **#465** — Animationen. Fundament der Designsprache vor Fläche; berührt
   fünf zentrale Primitives, die jede spätere UI-Welle erbt.
4. **#430** — Angemeldet bleiben. Fläche. #429 ist gemergt, die harte
   Datei-Kollision damit aufgelöst.
5. **#427** — Agent-Favoriten. Fläche, öffnet nichts.

**Korrektur gegenüber dem Planentwurf:** #458 stand zunächst auf Platz 2
hinter #463. Zwei Funde aus der Kollisionsprüfung drehen das:

- #458 trägt eine **harte** Abhängigkeit (#454), #463 keine — Kriterium 1
  schlägt Kriterium 2, obwohl beide zum Cloud-Block gehören.
- #458 kollidiert mit **#430** an `deploy/hetzner/.env.example`. Die alte
  Queue führte diese Datei nur unter „#429 ↔ #430"; mit dem Merge von #429
  wäre die Zeile ersatzlos verschwunden und die Kollision unsichtbar
  geworden. Sie lebt jetzt als „#458 ↔ #430" weiter.

**Blockiert, nicht einplanbar:** #453 (CI-Weg), #462 (Priorität), #436
(Fehler-Vokabular). #462 fehlte in der Warteschlange bislang **ganz** und ist
jetzt als blockiert aufgenommen.

## Wellen

| Welle | Pakete | Warum gemeinsam |
|---|---|---|
| 1 | #458 · #463 · #465 | Drei getrennte Stacks: `deploy/hetzner/.env.example` · `packages/billing/**` · `apps/web/src/{styles,components/ui}/**` |
| 2 | #430 · #427 | `config.ts` + `LoginPage.tsx` + Deploy-Vorlage gegen OpenAPI-Artefakte + `client.ts`; #430 erst **nach** #458 |

#427 und #430 lagen bisher in getrennten Wellen, weil #427 die
OpenAPI-Artefakte mit dem blockierten #436 teilt. Untereinander sind sie
disjunkt — solange #436 blockiert ist, können sie zusammen laufen.

Zwei Kollisionszeilen sind neu und vorher nirgends notiert: **#463 ↔ #462**
(latent, gemeinsame Testdateien, tritt erst bei Freigabe von #462 ein) und
**#465 ↔ #431-Wellen** (die sechs Motion-Dateien gehören beim Zuschnitt von
W1–W4 freigehalten).

## Was der Lauf nicht tut

Kein Code, kein Branch für die Issues, kein Issue-Claim, keine neuen Issues.
Die drei aus #463 herausgelösten offenen Punkte bekommen **kein** eigenes
Issue — das wäre „GitHub-Artefakt anlegen & pflegen“ und braucht erst die
Owner-Antwort.

## Ergebnis

Ausgeführt am 2026-09-06. Gegen-Read über `list_issues` bestätigt für alle drei
veredelten Issues Titel, Labels und Archiv-Kommentar.

| Issue | Vorher | Nachher | Belege im Body |
|---|---|---|---|
| #458 | `bug`, `needs-decision` | `bug`, `agent-ready`, `size/S` | 3 Compose-Kombinationen selbst durchgespielt |
| #465 | `bug`, `web`, `needs-decision` | + `agent-ready`, `size/S` | Build-Grep über `dist/assets/*.css` |
| #463 | `enhancement`, `backend`, `needs-decision` | + `agent-ready`, `size/S` | 7 Fundstellen einzeln nachgeprüft |
| #442 | Queue von 2026-09-05 17:05 | neu geordnet, 5 Einträge + 3 blockierte | — |

Verifikation der Befunde (jeweils selbst ausgeführt, nicht übernommen):

- **#458:** `docker compose config` gegen `../.env.example` für alle drei
  Overlay-Kombinationen — ohne `MINIO_ROOT_PASSWORD` bricht **jede** ab, mit
  ihr löst **jede** auf. `MINIO_ROOT_PASSWORD` ist der einzige `:?`-Guard im
  Verzeichnis; vier weitere Pflicht-Secrets derselben Vorlage tragen
  `CHANGE_ME_`.
- **#465:** `npm run build` → `dist/assets/index-*.css` enthält **keinen** der
  vier Klassennamen (`animate-in`, `fade-in-0`, `zoom-in-95`,
  `slide-in-from-top`); einziges `@keyframes` ist `pulse` (Tailwind-eigen, für
  Skeletons laut Designsprache §7.3 so gewollt). 42 tote Klassen-Vorkommen über
  fünf Dateien. Der Befund war im Issue als „vermutet" markiert — er ist jetzt
  belegt.
- **#463:** Logger liegt bei `router.py:59`, der Mollie-Pfad protokolliert bei
  `:276` und `:339` — **nicht** bei `:262`, wie das Issue schrieb; im veredelten
  Body korrigiert. `_coerce_int` bei `webhook.py:105`, altes Muster noch bei
  `:161`. `_require_cloud()` → 404 bei `:78`, Signaturfehler → 400 bei
  `:184-188`; das Orakel aus Punkt 1 ist damit bestätigt.

### Was offen zurückgeht

- **#463 Punkte 1 + 3** — Kommentar mit drei Wegen für das 404/400-Orakel
  (Empfehlung B: Verhalten lassen, Docstring korrigieren) und einer Ja/Nein-
  Frage zum Dedupe-Namensraum. Blockiert das Paket nicht.
- **#462** — Optionen standen bereits im Body; kein Duplikat-Kommentar
  geschrieben. Braucht eine Prioritäts-Antwort.
- **#453** — CI-Weg A/B/C, Kommentar vom 2026-09-05 steht.
- **#436** — Fehler-Vokabular A/B/C, Kommentar vom 2026-09-05 steht.

### Nicht getan, bewusst

Keine neuen Issues (das wäre „GitHub-Artefakt anlegen & pflegen"), kein
Zuschnitt von #431 W1–W4 (Projekt-Blueprint), kein Code an den Issues, kein
Claim. #454 und #338 tragen `human-only` — der Lauf endet dort nach Schritt 1
des Playbooks.

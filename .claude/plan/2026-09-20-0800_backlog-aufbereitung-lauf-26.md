# Backlog-Aufbereitungslauf 26 — luetzey/who2be

**Datum:** 2026-09-20 · **Basis:** `main` @ `69bfeda` · **Vorlauf:** Lauf 25 (2026-09-19, `fd53b01`)
**Playbook:** Issue-Refinement (290b0c4f) · **Norm:** Agent-ready Arbeitspaket (73a86231)

## Auftrag

1. Jedes offene Issue gegen die Norm "Agent-ready Arbeitspaket" pruefen.
   Belegtes selbst entscheiden und mit Beleg ins Issue; Urteilsfragen als
   Kommentar mit drei Optionen + Empfehlung, Issue auf `needs-decision`.
2. Warteschlange (`backlog-queue`, #442) neu ordnen: harte Abhaengigkeit >
   Owner-Vorgabe > Fundament vor Flaeche > Inventar vor Zuschnitt > bei
   Gleichstand das kleinere. Dazu Wellen (datei-disjunkt + stack-getrennt).
3. Bericht in drei Bloecken: selbst erledigt / braucht Owner-Antwort /
   Reihenfolge + Wellen.

## Ausgangslage (gelesen, nicht angenommen)

17 offene Issues. Davon:

- **Neu am 2026-09-19, nie durch Refinement:** #535 (Tracking Cloud-Haertung)
  mit Kindern #536-#540, dazu #541 (Backup) und #542 (Rechnung, `human-only`).
- **Bestand:** #520, #517 (`agent-ready`), #499, #428, #431, #435, #442,
  #454, #338.
- Lauf 25 (2026-09-19) hat die acht neuen Issues als Kommentar an #442
  vermerkt, aber **nicht** in den Body eingetragen — Begruendung dort:
  Body-Kapazitaet.
- `human-only` → Lauf endet dort (Playbook Schritt 1): #542, #454, #338.

## Leitfund dieses Laufs

**`main` hat sich bewegt — erstmals seit Lauf 17.** `fd53b01` → `69bfeda`,
20 Commits, 27 Dateien, **+120 Zeilen in `.github/workflows/ci.yml`**.

Konsequenz: die acht neuen Issues sind auf `8411173` gemessen, das Queue-Issue
auf `fd53b01`. **Jede zitierte `ci.yml`-Zeilennummer in jedem Issue und in
#442 ist damit unbelegt**, bis sie neu gemessen ist (Regel 16 + Regel 43 +
Vorschlag Regel 58 aus Lauf 24: "die Zeiger wandern").

Das ist kein Nebenbefund: die Verifikations-Bloecke sind das kritischste
Pflichtfeld der Norm, und ein Zeiger auf die falsche Zeile ist genau der
Fall, vor dem das Anti-Pattern "Verifikations-Kommandos erfinden" warnt.

## Zweiter Fund: die Kapazitaets-Blockade loest sich durch das Playbook selbst

Lauf 22-25 fuehren "was weicht aus diesem Body?" als **Owner-Urteil**, weil
Verdichten Verlust waere: 22 von 28 Historien-Eintraegen existieren nur im
Body. Lauf 25 schliesst daraus: "Lauf 26 kann diesen Body nicht mehr
aktualisieren" (23 Zeichen Reserve nach dem Lauf-25-Edit).

**Nachgemessen: 65.178 von 65.536 Zeichen, 358 frei — die Rechnung haelt.**

Aber die Praemisse der Frage haelt nicht mehr, sobald Schritt 5 des
Refinement-Playbooks angewandt wird: er verlangt ohnehin, den bisherigen Body
**woertlich als Kommentar zu archivieren, BEVOR** er ersetzt wird. Nach dieser
Archivierung ist Verdichten kein Verlust, sondern ein Umzug — und genau das
ist Schritt 1 von Option B'.

Damit ist die Blockade **belegt aufloesbar, ohne die Owner-Frage zu
praejudizieren**: das Archiv entfernt nichts und verbraucht keine der drei
Optionen. Was weiterhin Urteil bleibt, ist die Dauerform (A/B'/C) — die geht
als Frage an den Owner.

Historien-Block gemessen: **8.916 Zeichen** — das ist der Verdichtungsraum.

## Arbeitspakete (Sub-Agents, datei-disjunkt, alle read-only)

| WP | Inhalt | Modell | Begruendung |
|---|---|---|---|
| WP-1 | Repo-Fakten neu messen auf `69bfeda`: alle `ci.yml`-Jobzeilen, Web-Gates (lint/tsc -b/test:coverage), Python-Suite inkl. `collected`, GoTrue-Pins, Docker-Daemon | sonnet | mechanisch, Kommandos stehen fest |
| WP-2 | Norm-Pruefung + Zeiger-Verifikation #536, #537, #538 (Backend-Cluster) | sonnet | Lesen + grep gegen benannte Dateien |
| WP-3 | Norm-Pruefung + Zeiger-Verifikation #539, #540, #541 (Infra-Cluster) | sonnet | dito |
| WP-4 | Norm-Pruefung Bestand: #520, #517, #499 — halten die Angaben auf `69bfeda`? | sonnet | Nachmessung bekannter Zahlen |
| WP-5 | Tracking-Issues #428, #431, #435, #535 — Ist-Zustand gegen Body (Regel 22) | sonnet | Zaehlen + abgleichen |

Alle Sub-Agents: **read-only**, kein git-Schreibbefehl, kein Branch, kein
Issue-Write (Regel 30/45, Playbook-Anti-Pattern "Code anfassen").
Die Triage (entscheidbar vs. needs-decision) bleibt beim Orchestrator.

## Danach (Orchestrator)

- Konsolidieren: welche Issue-Bodys brauchen eine Korrektur, welche Weiche
  ist belegt, welche braucht Urteil.
- Body-Korrekturen: Original vorher als Kommentar archivieren (Schritt 5).
- #442 neu ordnen. **Kapazitaets-Warnung beachten:** der Body stand in Lauf 24
  bei 65.178 von 65.536 Zeichen — 358 frei. Ersetzen, nicht anhaengen.
- Bericht in den drei geforderten Bloecken.

## Was dieser Lauf NICHT tut

- Kein Code, kein Branch, kein PR im Produktivcode (Refinement-Playbook).
- Kein `agent-ready` ohne einzeln abgehakte Pflichtfelder.
- Keine Weiche entscheiden, die Urteil braucht (Produktzahlen der Tarife).
- Kein Zuschnitt von `size/M` (Regel 7 — das waere Projekt-Blueprint).

---

# Ergebnis des Laufs (2026-09-20)

## Korrektur der eigenen Eingangsthese

Der Plan oben sagt: "jede zitierte `ci.yml`-Zeilennummer ist unbelegt".
Als Vorsichtsannahme richtig, als Befund zu stark. Nachgemessen:

| Anker | fd53b01 | 69bfeda |
|---|---|---|
| changes / python / web | 17 / 81 / 159 | unveraendert |
| lint / tsc -b / test:coverage / a11y / build | 176/178/182/194/196 | unveraendert |
| Doku-Allowlist | 72-76 | unveraendert |
| compose-smoke | 224 | unveraendert |
| openapi-Gate | 126-131 | 127-128 |
| Python-Testlauf | 147-150 | unveraendert (byte-identisch) |
| **e2e** | 250 | **252** |
| **e2e-billing-cloud** | 295 | **299** |
| **audit** | 366 | **375** |

Die +120 Zeilen sind fast vollstaendig ans Ende gewandert (OSV-Scan,
npm-audit-Haertung). Drei Anker haben sich bewegt, nicht alle.

## Eigener Verfahrensfehler

WP-1 und WP-4 wurden gleichzeitig im selben Arbeitsbaum gestartet und
fuhren beide Web-Gates. WP-1 brach ab mit
`Something removed the coverage directory ... Vitest created earlier`.
Das ist Regel 31 des Repos, angewandt auf die Pruefung statt auf die
Umsetzung — und die Wellen-Regel verlangt fuer zwei Pakete im selben
Stack getrennte Worktrees. Der Fehler liegt beim Orchestrator, nicht bei
den Agenten (Regel 30: die Wellen-Bedingungen gelten auch fuer ihn).

Entlastung: WP-4 hat seine 66/69/66-Messungen **vor** dem Nebenlauf
erfasst und sie sind reproduzierbar; die Python-Zahlen habe ich selbst
seriell nachgemessen. Die Befunde stehen, die Lehre bleibt.

Konsequenz fuer die Liste: die Wellen-Bedingung gilt ausdruecklich auch
fuer Lese-Agenten, die Gates fahren. Steht so im neuen Body von #442.

## Zeiger-Bilanz — elf gewanderte Zeiger an sieben Issues

Ursache in zwei Commits desselben Tages:
- `8f13481` (SeaweedFS statt MinIO, 2026-09-19 08:09): +13 ab `auth:` in
  docker-compose.yml
- `960520a` (Blobstore-Absatz): +1 ab ~Zeile 74 in CLAUDE.md
- die ci.yml-Haertung: +2/+4/+9 bei drei Jobs

| Issue | Zeiger | alt | neu |
|---|---|---|---|
| #517 | CLAUDE.md (4 Stellen) | 135/148/151/233 | 136/149/152/234 |
| #499 | docker-compose.yml Pin | 50 | 63 |
| #499 | docker-compose.yml MFA | 70-74 | 83-87 |
| #499 | ci.yml e2e | 250 | 252 |
| #499 | ci.yml Billing-Guard | 340-342 | 349-351 |
| #539 | docker-compose.yml Pin | 50 | 63 |
| #536 | entity_quota_service.py is_cloud | 71 | 75 |
| #536 | entity_quota_service.py Datenverlust | 12-15 | 7-10 |
| #537 | mcp_limit_service.py Kommentar | 94 | 93 |
| #537 | core/rate_limit.py | 39-47 | 40-47 |
| #538 | entity_quota_service.py is_cloud | 71 | 75 |
| #538 | routers/tokens.py rotate_token | 72 | 73 |
| #428 | ci.yml e2e-billing-cloud | 295 | 299 |

Dazu zwei Fehler, die keine Zeilenverschiebung sind:
- #536 verortet `CLOUD_FREE_ENTITLEMENT` in `plans.py`; es liegt in
  `licensing/entitlement.py:122` — falsches Paket, nicht nur falsche Zeile.
- #538 nennt `POST /v1/tokens`; real `/v1/workspaces/{workspace_id}/tokens`.

**Der schaerfste Fall:** #539 wurde am 2026-09-19 11:09 angelegt — drei
Stunden NACH dem SeaweedFS-Commit. Der Zeiger `:50` war beim Anlegen
bereits falsch und wurde ungeprueft aus #499 uebernommen. Das ist der
Beleg fuer Regel-Vorschlag 58 aus Lauf 24.

## Zahlen, die nicht mehr halten

- Python-Suite: 1903/1418/485 -> **1992/1507/485** (+89 OAuth-Tests).
  Die 89 ist exakt die Billing-Testzahl — ohne die `collected`-Zahl waere
  Wachstum nicht von der Billing-Luecke unterscheidbar gewesen.
- #428 Option-B-Kosten: 17 Zeilen/8 Dateien -> **20/9**
  (docs/cloud-hosting-owner-guide.md aus PR #534).
- Offene PRs: 9 -> **11**; #489 weg, #533/#526/#527 neu.
- **#526 und #527 sind gegenstandslos** (anyio 4.15.1 ist in uv.lock;
  minio/mc existiert nicht mehr).

## Kapazitaets-Blockade aufgeloest

Schritt 5 des Playbooks (woertlich archivieren vor dem Ersetzen) macht
aus der Verdichtung einen Umzug. Body 65.178 -> 55.456 Zeichen,
10.080 frei. Die Dauerform bleibt Owner-Urteil.

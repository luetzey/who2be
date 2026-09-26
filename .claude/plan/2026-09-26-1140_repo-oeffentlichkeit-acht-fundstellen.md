# Repo-Oeffentlichkeit 2/3 — acht Fundstellen entschaerfen

**Karte:** t_2ef0060d · **Branch:** `who2be/t_2ef0060d-repo-oeffentlichkeit-2-3-acht-fundstelle`
**Grundlage:** Messbericht (nicht im Repo), Abschnitte 1, 4 und 7.
**Leitlinie:** Nenne den Zustand und die Entscheidung. Nenne nicht den Weg und
nicht die Rechnung.

## Vorbedingung geprueft

`RUNBOOK.md` wurde von `t_87ed8580` bearbeitet — **PR #641 ist MERGED**. Branch
auf `origin/main` `a2bf65df` per Fast-forward nachgezogen, Kollision damit
ausgeschlossen.

**Rest-Kollisionsrisiko RUNBOOK:** PR #652 (`t_1425a83c`) ist OPEN und aendert
`RUNBOOK.md` in den Hunks `@@ -11`, `@@ -63`, `@@ -408`, `@@ -483`, `@@ -938`.
Meine Aenderungen liegen bei Z. 794, Z. 1058 und Z. 1189 — **kein Overlap**.
Wird trotzdem als Hotspot an der Karte vermerkt.

## Der Entscheidungstest (vier Fragen, erste Ja-Antwort entscheidet)

1. Route/Datei/Zeile einer **heute offenen** Luecke?
2. Schritt-fuer-Schritt-Anleitung oder Grenzwert, ab dem ein Schutz nicht greift?
3. Rechnung, was ein Umgehungsweg kostet oder einbringt?
4. Preis, Marge, Deckungsbeitrag, Kunden- oder Umsatzzahl, die nicht schon
   veroeffentlicht ist?

## Was ausdruecklich BLEIBT (Gegenprobe im PR zu belegen)

`docs/adr/` (52 ADRs) · `docs/security-findings.md` und `-phase-2.md`
inhaltlich, insbesondere §9 F-Phase2-04 (vom Bericht als vorbildliche
Dokumentation bezeichnet) · `docs/compliance/` · `RUNBOOK.md` als Ganzes ·
`plans.md` „Bekannte Grenze 1/2" · `.claude/` als Verzeichnis ·
`gate_inventory.json` (**F1, eigene Karte — nicht anfassen**).

## Arbeitspakete

### AP1 — F2 `docs/cloud-hosting-owner-guide.md` (691 Zeilen) raus

**Entscheidung: die Datei geht ganz, kein Herausloesen des Installationsteils.**

Begruendung, gemessen statt geschaetzt:

* §2 („Schritt-fuer-Schritt") ist **kein exklusiver Inhalt**. Er verweist
  selbst durchgaengig auf `deploy/hetzner/RUNBOOK.md` §Provisioning, und die
  Owner-Vorbereitungsliste existiert seit 2026-09-25 als eigenes, neueres
  Dokument: `docs/cloud-erstinbetriebnahme.md` (435 Zeilen, Stand gegen
  `main@53c4b854`). Ein herausgeloester §2 waere eine **dritte** Fassung
  derselben Prozedur — genau die Doppelpflege, die der Bericht §7 als
  Scheiterstelle benennt.
* Die drei Abschnitte, die §2 tatsaechlich exklusiv traegt, sind klein und
  ziehen sauber um (AP1b): das SSH-Hardening-Snippet, der
  `unattended-upgrades`/`fail2ban`-Hinweis und der Owner-Schritt „AVV mit
  Hetzner abschliessen".
* Der Rest der Datei ist nicht rettbar: zwei Abschnitte sind Preisstrategie
  (Testfrage 4 — Tarifvorschlag mit Preisen, Deckungsbeitrag, Annahme zur
  Zahlerquote), einer ist eine nach Prioritaet sortierte Luecken-Liste mit
  Codezeigern (Testfrage 1+2), zwei weitere sind Betriebszustand (Datenhaltung
  mit Owner-Ansprache, Wiederherstellbarkeit). Eine halbe Datei waere schlechter
  als eine klare Trennung. Die Fundstellen im Einzelnen stehen in der
  Kartenbeschreibung.

Schritte:

1. Inhalt **unveraendert** nach `/home/luetzey/intern/cloud-hosting-owner-guide.md`
   sichern (ausserhalb jedes Repos). Wohin sie spaeter wandert, entscheidet der
   Owner — **kein** Umzug in `luetzey/who2be-website`.
2. `git rm docs/cloud-hosting-owner-guide.md`.
3. **Tote Verweise:** die erschoepfende Suche (`git grep` ueber alle getrackten
   Dateien, drei Muster) liefert 12 Treffer. Genau **einer** ist ein echter
   Markdown-Link: `docs/README.md:69`. Die uebrigen 11 sind nackte
   `datei:zeile`-Textzeiger in 4 Plandateien und 1 Changelog-Fragment — nach
   `docs/code-references.md` §Altlast bewusst nicht nachzukorrigierender
   Bestand, und `scripts/check_code_refs.py` stuft sie als `legacy` (nicht rot)
   ein. Belegt: mit entfernter Datei laeuft `check_code_refs.py .` mit
   **0 error** durch. Ein Link-Checker existiert in CI nicht (geprueft).
4. `docs/README.md:69-74` ersetzen: kein toter Link, sondern ein Zeiger auf die
   drei oeffentlichen Nachfolger (Erstinbetriebnahme, RUNBOOK, plans.md) plus
   ein Satz, dass der Owner-Leitfaden nicht oeffentlich liegt.

### AP1b — die exklusiven unbedenklichen Substanzen nachziehen

Bei der Umsetzung geprueft und **auf einen Punkt zusammengeschrumpft**:

* SSH-Hardening und automatische Host-Updates: **nichts zu tun.** Der offene
  PR #652 (`t_1425a83c`) fuegt beides schon ins RUNBOOK ein, und zwar besser als
  die Vorlage — als sshd-Drop-in mit `sshd -t`-Vorpruefung statt `sed` auf der
  Hauptdatei, plus Protokollabschnitt. Ein eigener Absatz waere eine dritte
  Fassung derselben Prozedur und dazu eine Merge-Kollision. Verworfen.
* Die UFW-/Cloud-Firewall-Begruendung: **nichts zu tun.** Steht seit #641/#652
  laenger und mit Docker-Zitat im RUNBOOK §4.
* `docs/cloud-erstinbetriebnahme.md` Phase 0: Owner-Schritt „AVV mit Hetzner
  abschliessen" **ergaenzt** — er war bisher nur ein `<PLATZHALTER>` in
  `docs/compliance/vvt.md` und nirgends ein Handlungsschritt. Mit
  „kein Rechtsrat"-Hinweis.

### AP2 — F3 `docs/licensing/plans.md` „Bekannte Grenze 3"

Tatsache bleibt (`POST /organizations` ohne Obergrenze gehoert in eine ehrliche
Tarifbeschreibung — Vertragsinhalt). **Weg geht die Aufwandskalkulation** des
Umgehungspfads, hier und im Absatz „Gueltigkeitsbereich dieser Entscheidung"
(Testfrage 3; der genaue Wortlaut steht in der Kartenbeschreibung, nicht hier).
Der Grund selbst — eine neue Org faellt auf das Free-Entitlement zurueck und
braucht eigene Bestaetigung — bleibt stehen, ohne Zahlen. Selbsttragend pruefen.

### AP3 — F5 `deploy/hetzner/RUNBOOK.md`

* Restore-Drill-Protokolltabelle: die leere Platzhalterzeile entfernen und durch
  die Auflage ersetzen, jeden Drill dort einzutragen. Der **Abschnitt** bleibt
  vollstaendig; was geht, ist eine oeffentlich lesbare Aussage ueber den
  Protokollstand (Betriebszustand, im Code nicht enthalten).
* Rotations-Abschnitt („bricht … **still** ab") → den Fehlerfall benennen und auf
  den Alarmweg zeigen, statt die Stille als Eigenschaft zu behaupten.
* Alarmweg-Abschnitt: beschreibt einen **behobenen** Zustand (Testfrage 1:
  geschlossene Luecke = erlaubt und erwuenscht). Nur die Ausmalung des
  Schadensbilds kuerzen, die Entscheidung und ihr Grund bleiben.
* **Nicht** angefasst: der Hinweis zum Cron-Ausfall im Access-Log-Abschnitt (eine
  Pruefanleitung, kein Betriebszustand), der SeaweedFS-Migrationshinweis
  (Owner-Anleitung fuer einen Umbau, kein Ist-Zustand der Produktion; viermal
  Nein) und die LUKS-Verifikationstabelle (aus #641, gehoert nicht zu F5).
* Der Bericht nennt zusaetzlich einen als offen markierten Blob-Backup-Punkt —
  **gegenstandslos**: seit PR #645 sichert der naechtliche Lauf alle drei
  Bestaende, und das RUNBOOK sagt das auch. Nichts zu tun.

### AP4 — F6 zwei Changelog-Fragmente

* `changelog.d/workspace-quota.added.md`: der Vorzustand war als Rezept
  formuliert („ohne Deckel …") — die Aenderung beschreiben statt den Weg dorthin
  (Testfrage 2).
* `changelog.d/w8p5-artifact-text-speicher-quota.changed.md`: die genannte
  Durchsatz-Zahl ist das Produkt aus Rate-Limit und Zeichengrenze, also eine
  Ausnutzungsrechnung (Testfrage 3). Die Verhaltensaenderung, das Byte-Zaehlen
  und alle Routen bleiben.
* `changelog.d/w8p3-waechter-tests-stille-luecken.added.md` ist der **Wegweiser
  zu F1**. Da F1 einer eigenen Karte gehoert, entferne ich hier nur den Satz,
  der die Datei als Fundort von Begruendungen ungegateter Routen ausweist — der
  Test selbst und das Golden bleiben genannt.

### AP5 — F4 zwei Praemissen-Saetze

`docs/security-findings.md:285-287` und `docs/security-findings-phase-2.md:367`
bzw. `369-371`: „solange das Repo privat ist" / „Repo bleibt privat" stimmen
nicht mehr. **Nicht entkernen** — der Befund und seine Bewertung bleiben
wortgleich; nur die gekippte Praemisse wird durch den heutigen Stand ersetzt
(Repo ist oeffentlich, F-Phase2-01 ist seit 2026-06-03 geschlossen, der Satz ist
historisch). §9 F-Phase2-04 bleibt unangetastet.

### AP6 — F7 zwei Plandatei-Stellen

* `.claude/plan/2026-09-05-1520_cloud-launch-readiness-inventar.md:65` formuliert
  den Zustand eines nicht durchgesetzten Feature-Codes so, dass der Satz im
  Streitfall gegen den Betreiber verwendbar ist. Sachlich benennen und auf die
  Einordnung in `plans.md` zeigen; die Zeile bleibt als Befund erhalten.
* `.claude/plan/2026-09-22-0100_538-token-quota-je-workspace.md:109` beschrieb
  den Multiplikator als Weg; er ist inzwischen durch den Workspace-Deckel
  geschlossen. Stand nachziehen statt Rezept stehen lassen.

### AP7 — Changelog-Fragment + Gegenprobe

Fragment unter `changelog.d/`, das **nichts von den Fundstellen zitiert** (die
Regel gilt auch fuer diesen PR selbst). Gegenprobe im PR: `git diff --stat`
zeigt keine Datei unter `docs/adr/`, `docs/compliance/` und keine inhaltliche
Aenderung an den Findings-Befunden.

## Verifikation

1. `uv run python scripts/check_code_refs.py .` → 0 `error`.
2. `uv run python scripts/changelog_fragments.py check` und `guard --base origin/main`.
3. `git grep cloud-hosting-owner-guide` → nur die bewussten Legacy-Textzeiger,
   kein Markdown-Link.
4. `git diff --stat origin/main` als Gegenprobe fuer ADRs/Compliance/Findings.
5. CI gruen gegen den exakten Head-SHA.

## Out of Scope

`gate_inventory.json` (F1) · Golden File · Historie umschreiben · Schreibregel
verankern (`t_23bac5e4`) · Repo auf privat stellen · Umzug nach
`luetzey/who2be-website`.

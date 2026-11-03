# Backlog-Aufbereitungslauf 61

**Datum:** 2026-10-25
**Messpunkt:** `main` @ `3d55f09c` (`feat(billing,web): Rechnungen im Web, Liste und PDF-Download (Rechnung R3)`, #1088)
**Fenster seit dem letzten Messpunkt (`12093b46`):** **14 Commits**
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit,
Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und
in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — zwölfter Lauf in Folge.**
Der Server steht in der Sitzung als autorisierungspflichtig; `ToolSearch` liefert keine seiner
Werkzeuge. Persona und Playbook-Katalog lagen im System-Prompt vor; `get_persona`,
`list_triggers`, `fetch_playbook`, `fetch_resource` (darunter die Norm „Agent-ready
Arbeitspaket", `73a86231`), `record_usage`, `submit_feedback` und `search_memory` nicht.
Der Lauf fährt deshalb nach dem reduzierten Kern des Bootstrap-Skills, nach dem Body von #442
und nach `.github/PROJECT.md`. **Zwölfter Lauf ohne Kurations-Rückmeldung an die eigene
AgentDB** — die vier Pflichtfelder der Norm stammen aus der in Lauf 55 protokollierten
Fassung (belegter Befund · Scope „In" **und** „Out" · 2–5 prüfbare Akzeptanzkriterien ·
ausführbare Verifikations-Kommandos).

**Kein passendes Playbook ladbar.** Dem Anliegen am nächsten kommt „GitHub-Artefakt anlegen &
pflegen" (`d5995b1b`); ohne MCP ist es nicht abrufbar.

## Messgrundlage

Alle Werte am 2026-10-25 auf `main` @ `3d55f09c` erhoben, sequenziell (ein Schreiber je Baum),
Node **v22.22.0**, **ohne vorherige Reparatur** (Regel 120), **Exit-Codes ohne Pipe** (Regel 94).
Der Klon war **shallow** (50 Commits, Voreinstellung dieser Umgebung); nach `git fetch
--unshallow`: **1657** Commits (Regel 90).

| Gate | Ergebnis | Vorlauf |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, 0 Funde | — |
| `uv run mypy .` | **Exit 0**, **652** Dateien | 649 |
| `uv run pytest --collect-only -q` | **Exit 0**, **4957** Tests, **312** unter `packages/billing/` | 4882 / 276 |
| `scripts/changelog_fragments.py check` | **Exit 0**, **394** Fragmente | 380 |
| `npm run lint` | **Exit 0**, **0 errors / 94 warnings**, 7 `--fix`-bar | 93 |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | — |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen | 156 |
| `npm run test:coverage` | **Exit 0**, **282** Dateien / **2848** Tests, **359,79 s** | 280 / 2780 / 333 s |
| Coverage Web | **89,89 / 83,95 / 86,81 / 91,75** | 89,74 / 83,78 / 86,60 / 91,56 |
| `npm audit --omit=dev --audit-level=high` | **Exit 0** | — |
| 🔴 `npm audit` (mit dev) | **rc 1**, **1** Advisory (`http-cache-semantics`) | rc 1, 2 |
| 🟢 `pip-audit` wie in CI (`ci.yml:973-975`) | **rc 0**, „No known vulnerabilities found" | 🔴 rc 1, 5 Advisories |
| `main`-CI | Lauf **2324**, `status: completed` **und** `conclusion: success` getrennt gelesen (Regel 91) | 🔴 2284 `failure` |
| `docker info` | **Exit 1**, kein `podman` — **37. Messung in Folge** | — |

**Fundstellen, einzeln gelesen:** `MfaSection.tsx` **297** Zeilen (0× bewegt) · `LoginPage.tsx`
**399** (0×) · `api/client.ts` **1.849** (1×) · `e2e/helpers/auth.ts` **199** (0×) ·
`e2e/billing.spec.ts` **321**, **5** Tests, `grep -c invoice` → **6** ·
`docs/mcp-payload-budget.md` **573** (0×) · `docs/compliance/gobd-verfahrensdokumentation.md`
**144** (0×) · `docs/licensing/plans.md` **271** (0×) · `ci.yml` **1.259** ·
`deploy/hetzner/Caddyfile` **208**, `grep -cE "\brate\b"` → **0** · `vite.config.ts` **107**,
Schwellen `:99-104` (Branches **79**) · `osv-scanner.toml` **1×** `[[IgnoredVulns]]`,
`ignoreUntil = 2026-11-02T00:00:00Z` · `orphan-baseline.json` **156** Einträge, Pfad
`apps/web/src/i18n/` · Locales **3.364 / 3.364** · GoTrue **v2.197.0** an allen drei Stellen ·
Betriebs-Caddy `caddy:2.11.7-alpine` (`docker-compose.yml:480`) gegen CI `caddy:2.8-alpine`
(`ci.yml:381/382/397/398`) · `uv.lock`: `fastmcp` **4.1.3**, `pypdf` **6.21.2** ·
`package-lock.json`: `undici` **6.29.1**, `http-cache-semantics` **4.2.0**.

**PR-Scopes** je `git merge-base` + `git diff --name-only` mit Nicht-leer-Prüfung über alle
**13** offenen PRs.

## Das Ergebnis in einem Satz

🟢 **`main` ist grün, und beide Supply-Chain-Ursachen von Lauf 60 sind weg** — aber zwei der
drei Pakete, die Lauf 60 dafür geschnitten hat, waren **binnen eines Tages schon gebaut**, von
Trägern, die die Issues nicht kennen.

## 1. Selbst erledigt

### 1.1 #1076 geschlossen — der eigene Eskalationsfall ist eingetreten

Der Body nennt als dritten Eskalationsfall: „`main` ist beim Start schon grün → dann hat jemand
anders gebumpt; Versionen nachmessen und das Issue schließen statt doppelt zu arbeiten."

**Träger: `475c0dc0` (#1074), gemergt 2026-10-24 07:40 — 7,5 Stunden nach dem Anlegen.**
#1074 hat seinen Scope um den undici-Bump erweitert und beide Ursachen in einem PR behoben,
genau wie #1076 §Vorentschieden es empfohlen hatte. **Das Issue ist im PR nicht genannt.**

Alle fünf Kriterien nachgemessen: `undici` **6.29.1** · `npm audit` ohne Schlüssel `undici` ·
`osv-scanner.toml` unverändert **1** Block, kein neuer · nur das Lockfile bewegt, nicht
`package.json` · Web-Gates je **Exit 0**. Dazu die Gegenprobe auf den Zweck: `pip-audit` **rc 0**,
CI-Lauf 2324 `success`, der OSV-Schritt läuft wieder statt `skipped` zu sein.

### 1.2 #1077 aus der Warteschlange genommen — ein offener PR liefert es vollständig

**Das ist der Fund dieses Laufs.** #1077 wurde am 2026-10-24 00:22 geschnitten; um **20:57**
desselben Tages hat **PR #1087** (`R2d`) geöffnet und dieselbe Datei umgeschrieben —
`Issue: n/a`, Kanban-Karte `t_60600cd1`.

Gemessen an `git show pr-1087:docs/compliance/gobd-verfahrensdokumentation.md` (**231** Zeilen,
auf `main` **144**; `+122/−35`):

| AK von #1077 | PR-Fassung | auf `main` |
|---|---|---|
| 1 — drei Negativ-Greps | 🟢 **0 / 0 / 0** | 2 / 1 / 1 |
| 2 — vier Artefakte, jedes ≥ 1× | 🟢 `billing_invoice` 4×, `payment_id` 2×, `invoice-retry` 2×, `invoices/` 2× | je **0** |
| 3 — `<PLATZHALTER`-Zahl sinkt nicht | 🟢 **7 → 10** | 7 |
| 4 — §7-Historienzeile | 🟢 `:231`, Datum + Quelle `ADR-0061 §5, §7, §8; Pakete R2a–R2d` | fehlt |

Die eigene Behauptung „✅ **Keine Datei-Sperre** … von **keinem** der 18 offenen PRs angefasst"
ist damit falsch. **Konsequenz:** #1077 bleibt offen (der Träger ist nicht gemergt, er wartet
auf das Owner-Go für eine Compose-Änderung), ist aber **kein Paket mehr, sondern ein
Wartestand**. Wer es startet, baut einen Konflikt in genau der Datei, die der fertige PR
umschreibt. Fällt das Owner-Go aus und #1087 wird geschlossen, ist es unverändert startbar.

**Nebenbefund, mit Beleg richtiggestellt:** AK3 nannte als Startwert `grep -c "<PLATZHALTER"` →
**6**. Gemessen sind **7** — sechs echte Marken (`:84`, `:94`, `:127`, `:131`, `:133`, `:135`)
plus die Meta-Zeile `:7`, die die Konvention erklärt. Die Datei ist 0× bewegt; das war ein
Zählfehler beim Anlegen, keine Veralterung.

### 1.3 #989 — die Startbedingung neu gefasst, weil die Frist die Datei-Sperre schlägt

Der Body sagte: „Das Paket startet, wenn **BEIDE** Träger weg sind." Beide Lockfile-Träger
stehen heute schlechter als bei der Formulierung:

| Träger | Lauf 58 | heute |
|---|---|---|
| #1017 web-minor-patch | `clean`, **0** hinter `main` | **54** hinter — braucht Branch-Update |
| #674 Vitest 4 → 5 | **1** hinter | **55** hinter, an 8 Checks rot, **Weiche 12 seit 13 Tagen** |

**Wer auf „beide Träger weg" wartet, wartet auf eine unbeantwortete Weiche — und
`ignoreUntil = 2026-11-02` läuft in 8 Tagen ab.** Die Preise sind nicht symmetrisch: Warten
kostet ein rotes `audit` auf `main` ohne Code-Änderung (der Zustand, den Lauf 60 fand und der
26 Stunden unbemerkt blieb); Bauen kostet im schlechtesten Fall ein Neu-Auflösen des Lockfiles,
das beide Träger wegen 54/55 Commits Rückstand ohnehin brauchen.

Prämisse zum dritten Mal geprüft und gehalten: `npm view http-cache-semantics@latest version`
→ **4.3.0**, Lockfile **4.2.0**, `npm audit` mit dev **rc 1 / {high: 1}**, ohne dev **rc 0**.
**Entschieden: das Paket startet jetzt**, die Datei-Sperre ist Hinweis, nicht Blocker.

### 1.4 #1001 — Befund nachgemessen, hält unverändert

`uv run python -m who2be_mcp.payload_report` (Exit 0) liefert **103 / 108.251** — **zeichengleich
mit AK1**, obwohl zwei Builder-Pakete im Fenster am Katalog gearbeitet haben (`cb1c6547` B3,
`f9697fab` B6, `tool_policy` entdoppelt). Die Datei trägt weiter drei Stände; **108.251 kommt
in ihr nicht vor**, `71.749` auch nicht. Zeilen-Zeiger sind gewandert (`:233/:234` statt `:234`,
`:292` statt `:295`) — in einem Kommentar benannt. Datei über alle 13 PRs **frei**, 0× bewegt.

### 1.5 #632 / #633 — zwei Reihenfolge-Hürden sind weg

- 🟢 **Der Locale-Stau hat sich aufgelöst: sieben Träger → einer.** Nachgemessen über alle 13
  PRs: nur **#1084** fasst `de.json` an, und zwar zusammen mit `en.json` — nicht der schiefe
  Stand, vor dem Lauf 60 bei #1061 warnte. Schlüssel **3.364 / 3.364**.
- 🟢 **#633 hat wieder einen Verifikationsweg.** Lauf 60 hielt fest, dass dieses Paket als
  einziges nur in CI verifizierbar ist und bei rotem `main` **keinen** Weg hat. `all-green` ist
  grün → der Weg ist offen. Von drei Blockern bleiben zwei: #632 (hart) und die
  Container-Laufzeit.
- ⚠️ Richtiggestellt: der Pfad der Waisen-Baseline ist `apps/web/src/i18n/orphan-baseline.json`,
  in früheren Läufen ohne Verzeichnis genannt.
- 🔴 `e2e/helpers/auth.ts:33` bleibt unbelastbar — **199** Zeilen (beim Schnitt 180), ganz lesen.

### 1.6 Zwei alte Weichen durch Messung bzw. Handeln erledigt

- 🟢 **W25 — der `uv`-Updater ist nicht rot, er läuft.** **#1080** `deps: bump filelock from
  3.32.0 to 4.2.1`, Autor `dependabot[bot]`, Branch `dependabot/uv/filelock-4.2.1`, angelegt
  **2026-10-24 03:47**, `changed_files: 1`, Badge mit `package-manager=uv`. Dass #1074 von Hand
  kam, lag am Zeitdruck des roten Gates, nicht an einem toten Updater. Was bleibt, ist Triage
  eines Major-Sprungs — keine Weiche. **Lauf 60 hatte das als „ungemessen (403 des Proxys)"
  geführt; die Antwort lag die ganze Zeit in der PR-Liste.**
- 🟢 **W29 — `e2e-billing-cloud` ist erweitert.** `apps/web/e2e/billing.spec.ts`: **321** Zeilen,
  **5** Tests (waren 2), `grep -c invoice` → **6** (war 0). Neu `:284` und `:303`. Geliefert in
  **R3** (`3d55f09c`), nicht in R2. **Die Weiche war 24 Stunden alt und hätte nicht entstehen
  müssen** — s. §3.

### 1.7 #442 neu geschrieben

Warteschlange, Wellen, PR-Tabelle (18 → 13), Sperren-Tabelle, Weichen-Tabelle (20 → 19) und
§Funde ohne Issue vollständig gegen `3d55f09c` neu gesetzt. Neue Pflege-Regel **7**: ein Paket,
dessen Arbeit in einem offenen PR liegt, ist kein Paket, sondern ein Wartestand.

## 2. Braucht eine Owner-Antwort

**19 offene Weichen** (waren 20; −29, −25, +31). Die bestehenden werden nicht erneut gestellt
(Regel 9); in #442 steht je Zeile nur, was sich geändert hat. Vollständig neu ist eine:

### 🆕 Weiche 31 — Soll dieser Lauf überhaupt noch Implementierungs-Issues schneiden?

**Befund:** von den drei Paketen, die Lauf 60 am 2026-10-24 geschnitten hat, sind **zwei binnen
eines Tages vom Kanban-Strom erledigt worden**, ohne Kenntnis der Issues. #1076 (00:19) →
`475c0dc0` um 07:40, **+7,5 h**. #1077 (00:22) → PR #1087 um 20:57, **+20,5 h**, alle vier
schreibbaren AK erfüllt. Beide Träger tragen `Issue: n/a`. Im Fall #1077 war der Schnitt nicht
nur verloren, sondern **schädlich**: ein Agent, der startet, baut einen Konflikt.

- **A** — Der Lauf schneidet keine Implementierungs-Issues mehr und meldet Funde nur in #442.
  *Billigste Variante; der Preis ist, dass ein Fund keinen Griff mehr hat, über den ein
  unbeaufsichtigter Agent ihn findet — genau das Loch, das #442 zu schließen gebaut wurde.*
- **B** — Der Lauf schneidet weiter, prüft aber **vor** dem Anlegen jeden offenen PR gegen die
  geplanten Dateien (`git merge-base` + `git diff --name-only` je PR) und benennt einen
  gefundenen Träger im Issue, statt es als startbar zu melden. *Reine Messung, kostet eine
  Schleife über die offenen PRs, hätte #1087 sofort gefunden; fängt den Fall aber nur, wenn der
  PR beim Schnitt schon offen ist — bei #1074 war er es, bei #1087 nicht.*
- **C** — Die Kanban-Karten werden die Quelle, #442 spiegelt sie. *Löst die Ursache statt des
  Symptoms; braucht aber einen für Agenten lesbaren Kanban-Zugang, den es heute nicht gibt —
  eigenes Vorhaben, keine Antwort.*

**Empfehlung: B**, und dieser Lauf hat die Prüfung bereits angewandt — so ist #1087 gefunden
worden. **A** wäre richtig, wenn der Fall trotz B ein drittes Mal auftritt.

### Was sich an den bestehenden Weichen geändert hat (Kurzfassung)

- **30** (ADR-Nachtrag): 🟢 **Option A ist ab heute belegte Hauspraxis** — #1084 hängt an zwei
  `Accepted`-ADRs einen datierten „Nachtrag 2026-10-24". 🔴 Am auslösenden Fall (ADR-0061 §11,
  W61-1 bis W61-3) ist nichts geschehen. Offen ist nur noch: wer schreibt es hin.
- **28** (PM-Frage im PR-Body): hält jetzt **zwei** PRs — #1085 ist auf den Branch von #1054
  gestapelt.
- **26** (ADR-Pakettabelle): vierter Fall **aufgelöst, auf Seite A** — der Posten kam, nur ein
  Paket später.
- **24** (wer schließt ein gemergtes Issue): sechster Fall, und erstmals ist der Träger **noch
  offen** (#1077 / #1087). Der Mechanismus muss beide Fälle abdecken.
- **23** (Kanban außerhalb des Repos): 🔴 **14 von 14 Commits ohne Issue-Nennung**, drei davon
  ohne jeden Herkunftshinweis (`dfb2b4b5`, `35e7b0b6`, `78bf33ad`). 7 von 7 Code-PRs ohne Issue.
- **5** (`audit` im Required Check): 🟢 **Freispruch für die Blockier-Frage** — das Gate fing
  fünf Advisories auf einem Produktivpfad, die Reparatur war in 7,5 h da. 🔴 Die zweite Hälfte
  (ein Job, der alle vier Prüfungen meldet) bleibt.
- **8** (ESLint): 🔴 zweiter Anstieg in Folge, 90 → 93 → **94**, bei 0 errors und 7 `--fix`-baren.
- **6** (Coverage-Boden): n = 11, engster Abstand **4,95** Punkte (war 4,78).
- **12**, **17**, **9**, **15**, **7**, **18**, **22**, **2**, **4**: inhaltlich unverändert,
  Zahlen in #442 neu gemessen.
- **4** diesmal mit Kurzbeweis statt Wiederholung: **kein einziger der sieben
  Nicht-`agent-ready`-Bodies ist seit Lauf 60 angefasst** (`updated_at` alle vor dessen
  Messpunkt) — der dort protokollierte Norm-Stand gilt wörtlich weiter. Bewusst nicht umgebaut
  (Regel 7).

## 3. Reihenfolge und Wellen

**Kriterien in dieser Ordnung:** harte Abhängigkeit → Owner-Vorgabe → Fundament vor Fläche →
Inventar vor Zuschnitt → bei Gleichstand das kleinere.

| Pos | Issue | Baum | Kriterium, das entscheidet |
|---|---|---|---|
| **1** | **#989** `http-cache-semantics` → 4.3.0 | Web | **Owner-Vorgabe als Frist** — 8 Tage, danach rotes `audit` auf `main` ohne Code-Änderung |
| **2** | **#1001** Payload-Budget | Python | Fundament (die Referenz, gegen die andere messen); echt parallel zu 1 |
| **3** | **#632** Passkey registrieren | Web | öffnet #633; erstmals ohne Nebenbedingung |
| **4** | **#633** Step-up mit Passkey | Web | harte Abhängigkeit nach #632 |

| Welle | Pakete | Bäume | Disjunktheit |
|---|---|---|---|
| **A — jetzt** | **#989** ‖ **#1001** | Web ‖ Python | ✅ `apps/web/{package-lock.json,osv-scanner.toml}` gegen `docs/mcp-payload-budget.md` |
| **B — nach A** | **#632** | Web | allein — derselbe Vitest-Baum wie #989 |
| **C — parallel, kein Paket** | Merges #1087 (Owner-Go, schließt #1077) · #1054 → #1085 (gestapelt) · #1084 | — | drei Klicks |
| **D — nach B** | **#633** | Web | hart nach #632; zusätzlich Container-Laufzeit **oder** ein CI-Lauf |

**Billigste Merge-Reihenfolge:** #1084 → #1054 → #1085 → #1087 (nach Owner-Go) → #989 → #1017
(mit Branch-Update) → #1080 → #674.

## 4. Was dieser Lauf an sich selbst gelernt hat

- **Regel 142 (neu):** ein Fund wird vor dem Melden als startbar gegen die Dateien **aller**
  offenen PRs geprüft, nicht nur gegen `main`. Zwei Pakete in 24 Stunden dupliziert ist der
  Beleg; die Prüfung kostet eine Schleife und hätte #1087 sofort gefunden.
- **Bevor ein nicht gelieferter ADR-Posten zur Weiche wird, auch das nächste Paket der ADR
  prüfen.** Weiche 29 war 24 Stunden alt und hat sich an R3 selbst aufgelöst — sie hätte nie
  entstehen müssen.
- **Ein „ungemessen, Proxy 403" ist kein Endpunkt.** Weiche 25 hing drei Tage an einem
  unerreichbaren Job-Log; die Antwort stand die ganze Zeit sichtbar in der PR-Liste (#1080).

## 5. Nicht geschrieben, mit Begründung

- **`.claude/context/STATE.md` ist bewusst unberührt.** Der offene Protokoll-PR **#1078**
  (Lauf 60) ändert Kopfzeile und Anfang derselben Datei; ein zweiter Prepend erzeugt einen
  sicheren Konflikt zwischen zwei Protokoll-PRs. Der Inhalt, der dort hingehörte, steht
  vollständig in dieser Datei. ⚠️ **Hinweis an den, der #1078 mergt:** dessen STATE-Eintrag
  („`main` rot an zwei Supply-Chain-Funden") ist seit `475c0dc0` überholt — `main` ist grün,
  `pip-audit` rc 0, und von den beiden Funden ist nur `http-cache-semantics` (#989) offen.
- **Kein neues Issue angelegt.** Nach Weiche 31 Option B wurde jeder Kandidat gegen die offenen
  PRs geprüft; die drei Funde ohne Issue sind entweder Bewertungsfragen (#542) oder
  Richtigstellungen in bestehenden Bodies.
- **Die sieben Nicht-`agent-ready`-Bodies** sind nicht umgebaut (Weiche 4, Regel 7).

---

_Protokoll zu Aufbereitungslauf 61. Warteschlange: #442._

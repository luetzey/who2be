# Backlog-Audit gegen die Norm + Parallelisierbarkeit der Wellen

- Status: **abgeschlossen** (Read-only-Audit; ein Issue-Body korrigiert, kein Code)
- Datum: 2026-09-05, 12:15 UTC (15. Lauf)
- Auftrag: alle offenen Issues gegen den Issue-/Task-Standard prüfen, selbst
  lösbare Punkte lösen, Owner-Fragen sammeln, Reihenfolge und Gruppen bilden
- Norm: Resource *Agent-ready Arbeitspaket* (vier Pflichtfelder + fünftes ab
  Nicht-Trivialität), Playbook *Issue-Refinement*
- Vorgänger: 13. Lauf (Refinement, PR #439, gemerged), 14. Lauf (Reihenfolge,
  **PR #441 — offen als Draft**)

## 1. Befund in einem Satz

Der Backlog ist bereits agent-ready — die sieben `agent-ready`-Issues erfüllen
die Norm nachweislich, die Reihenfolge existiert. Was fehlt, ist **nicht
Refinement, sondern drei Owner-Klicks**: PR #441 mergen, zwei Weichen auf #428
entscheiden. Ohne den Merge zeigen zwei Issue-Kommentare auf einen Abschnitt,
den es auf `main` nicht gibt.

## 2. Audit — Pflichtfelder je Issue

Geprüft wurde jedes Feld einzeln am Body, nicht am Eindruck („sieht lang aus"
ist laut Norm der gefährlichste Fehler). `O` = Outcome/„Fertig heißt", `AK` =
2–5 von außen prüfbare Akzeptanzkriterien, `Out` = explizites Out-of-Scope,
`Ver` = exakte Kommandos + „grün heißt", `W` = vorentschiedene Weichen.

| Issue | Label | O | AK | Out | Ver | W | Urteil |
|---|---|:-:|:-:|:-:|:-:|:-:|---|
| #440 CI-Doku-Skip | `agent-ready` `size/S` | ✅ | ✅ 5 | ✅ | ✅ | ✅ 8 | Norm erfüllt. Vorbildlich: benennt selbst, dass eine CI-Änderung lokal nicht abschließend prüfbar ist, und verlangt vier Beleg-Runs. |
| #438 Responsive-Fundament | `agent-ready` `size/S` | ✅ | ✅ 5 | ✅ | ✅ | ✅ 6 | Norm erfüllt. AK „kein Konsument geändert" ist von außen per `git diff --stat` prüfbar. |
| #436 Fehlercodes W0 | `agent-ready` `size/S` | ✅ | ✅ 5 | ✅ | ✅ | ✅ 6 | Norm erfüllt. |
| #434 Readiness-Inventar | `agent-ready` `size/S` | ✅ | ✅ 6 | ✅ | ✅ | ✅ 8 | Norm erfüllt in der Ausprägung „Alltags-Task ohne Code": Verifikation ist eine Kette von Grep-Checks statt eines Testkommandos, plus Gegenprobe und Negativ-Listen-Check. |
| #430 Angemeldet bleiben | `agent-ready` `size/S` | ✅ | ✅ 6 | ✅ | ✅ | ✅ 10 | Norm erfüllt **nach der Korrektur in §3.1**. Weiche 6 (Cross-Tab-Logout) bleibt zulässig als Vermutung markiert. |
| #429 Coming-soon-Modus | `agent-ready` `size/S` | ✅ | ✅ 6 | ✅ | ✅ | ✅ 7 | Norm erfüllt. Weiche 2 korrigiert die Originalfassung sachlich (Compose kann keine Variable aus einer anderen berechnen) — genau die Art Fund, für die Refinement da ist. |
| #427 Agent-Favoriten | `agent-ready` `size/S` | ✅ | ✅ 7 | ✅ | ✅ | ✅ 11 | Norm erfüllt. |
| #435 Passkeys | `size/M` | ✅ | ✅ 5 | ✅ | ✅ | ✅ 4 | Feldseitig vollständig, aber **bewusst nicht startbar**: das Issue sagt selbst, es werde „nach Freigabe als Sub-Issues geschnitten". Korrektes `size/M` — laut Norm wird es nicht durch Aufblähen agent-ready. Siehe §5.4. |
| #428 Cloud-Launch | `epic` `size/M` `needs-decision` | ✅ | ✅ 5 | ✅ | — | teilw. | Tracking-Issue, richtig als `size/M` + `needs-decision`. Zwei Weichen offen (§4.1). |
| #402 Fehlercodes | `size/M` | ✅ | ✅ 5 | ✅ | ✅ | ✅ 5 | Tracking-Issue, W0 als #436 geschnitten. Korrekt. |
| #431 Mobile-UI | `epic` `size/M` | ✅ | ✅ 6 | ✅ | — | — | Tracking-Issue, W0 als #438 geschnitten. Korrekt. |
| #338 Owner-Checkliste | `human-only` | — | — | — | — | — | Lauf endet hier laut Playbook Schritt 1 — bewusste Entscheidung gegen Delegation, keine Lücke. |

**Ergebnis: kein `agent-ready`-Label ist zu Unrecht vergeben.** Die Label-Semantik
der Norm (S = in 10 Minuten reviewbar und startbar, M = braucht Aufteilung) ist
durchgehend korrekt angewendet.

Zwei Konsistenz-Nits, nicht behoben (Kosmetik, kein Delegations-Hindernis):
`#402` trägt kein `epic`, obwohl es wie `#428`/`#431` ein Tracking-Issue ist;
kein Issue trägt einen Milestone (0 von 12).

## 3. Selbst gelöst

### 3.1 #430 — Phantom-Referenz aufgelöst und ADR-Konflikt sichtbar gemacht

Weiche 8 verwies auf einen „Befund S1" in `docs/security-findings-phase-2.md`
und ließ offen, ob `docs/security-findings.md` gemeint war. Beides ist falsch,
per Grep verifiziert:

- `docs/security-findings.md` trägt F-01…F-13 — keiner mit Session-Bezug
  (F-11 ist „`VITE_*`-Fallbacks im Production-Build").
- `docs/security-findings-phase-2.md` trägt F-Phase2-01…03 (Rate-Limit,
  Cross-Workspace) — ebenfalls ohne Session-Bezug.
- Eine Kennung „S1" existiert im ganzen `docs/`-Baum nicht.

Gemeint ist **`docs/standards-review-2026-07-08.md:51` §SEC-2** — „Supabase-Session
im `sessionStorage` (`apps/web/src/lib/supabase.ts:13-33`) — per ADR-0035
gedeckte Ausnahme; Re-Visit-Trigger (Auth-BFF → httpOnly-Cookies) bleibt
bestehen", fortgeschrieben in `docs/standards-review-2026-07-20.md:122`.
Repo-belegt, damit nach Playbook-Schritt 4 selbst entscheidbar.

**Der schwerere Fund dahinter:** Weiche 1 von #430 (`localStorage` opt-in)
**revidiert `docs/adr/0035-web-session-storage-tradeoff.md`** (Status
„Akzeptiert", 2026-06-13). Dort ist `sessionStorage` genau deshalb gewählt,
weil eine persistente Ablage die XSS-Angriffsfläche vergrößert. Das Issue sah
dafür nur einen DECISIONS-Eintrag vor. Das reicht nicht: `docs/adr/` ist die
Heimat getroffener Architektur-Entscheidungen, und zwei widersprechende ADRs im
Repo wären der teuerste Ausgang. Als Weiche 10 ergänzt: es braucht eine
ablösende **ADR-0052**, ADR-0035 geht auf „Abgelöst". Scope, AK und DoD von
#430 sind entsprechend nachgezogen.

Das ist die einzige Stelle, an der dieser Lauf den Umfang eines Issues
erweitert hat — bewusst benannt, damit der Owner sie zurückdrehen kann; die
Originalfassung liegt als Archiv-Kommentar vom 2026-09-05 auf dem Issue.

### 3.2 Zwei Nebenfunde verifiziert, die als Vermutung im Backlog standen

- **`docs/reference/openapi.json` hat keinen Drift-Wächter** (#440 nennt es als
  Nebenfund). Bestätigt: `scripts/export_openapi.py:22` *schreibt* die Datei,
  kein Test und kein CI-Schritt *liest* sie; der Contract-Test vergleicht gegen
  `apps/api/tests/contract/openapi_surface.json`. Eine veraltete eingecheckte
  Spec fällt heute niemandem auf. → Vorschlag §5.1.
- **Typecheck-Kommando driftet an vier Stellen** (#427 nennt es am Rande).
  Bestätigt: `CLAUDE.md:151`, `CLAUDE.md:233`, `CONTRIBUTING.md:79` und
  `docs/CLAUDE-PROFILE.md:22` sagen `npx tsc --noEmit`; CI fährt `npx tsc -b`
  (`ci.yml`), `npm run build` ebenso. Die Doku widerspricht dem „lokal = CI"-DoD
  des Repos. → Vorschlag §5.2.

## 4. Was der Owner entscheiden muss

### 4.1 Zwei Weichen auf #428 (offen seit 2026-09-05, blockieren WP-2 und WP-4)

Beide sind Urteil, nicht Recherche — sie werden nicht geraten. Der Wortlaut mit
Belegen steht im Kommentar auf #428; hier die Kurzform:

1. **Pro-Feature-Gates informativ oder hart?** Die Codes `composite_playbooks`,
   `agents`, `audit_export` werden ausgegeben, aber nirgends erzwungen; einzige
   Durchsetzung ist `is_active()` in `services/mcp_limit_service.py:82`.
   **A** = informativ belassen (launchbar ohne Code, aber das BillingPanel wirbt
   mit Funktionen, die Free ebenfalls hat). **B** = hart gaten (402 + Upgrade-Hinweis;
   ehrliches Angebot, kostet ein eigenes WP und eine Regel für Bestands-Orgs
   über dem Limit). Empfehlung der Vorarbeit: **B**, weil `docs/licensing/plans.md`
   die SSoT der Tiers ist. Wer A wählt, muss `plans.md` und die Feature-Liste im
   Panel kürzen.
2. **Cloud-Image-Deploy: Registry-Pull oder Host-Build?** Offen seit
   `docs/standards-review-2026-07-20.md` §4 Nr. 5. **A** = Registry-Pull
   (reproduzierbar, gleicher Artefakt-Stand wie CI, braucht Registry-Login auf
   dem Host). **B** = Host-Build (kein Login, aber Build-Zeit auf der Prod-Box
   und CI-Image ≠ Prod-Image). Empfehlung: **A**, weil `deploy.yml` die Images
   ohnehin baut und pusht.

### 4.2 PR #441 mergen — der eigentliche Blocker

PR #441 („docs(project): Reihenfolge des Backlogs in PROJECT.md verankern",
Branch `claude/autonomous-code-agent-role-6x5vh4`) steht als **Draft offen**.
Er trägt den Abschnitt `§Reihenfolge` in `.github/PROJECT.md` — die erklärte
Quelle der Wahrheit für „welches Issue als Nächstes". Solange er nicht gemerged
ist, zeigen die Kommentare auf **#429** („Platz 2 in `.github/PROJECT.md`
§Reihenfolge") und **#434** („Platz 3") auf einen Abschnitt, der auf `main`
nicht existiert — geprüft: `grep -n "Reihenfolge" .github/PROJECT.md` → kein
Treffer. Ein Agent, der dem Pointer folgt, findet nichts und fällt auf Raten
zurück. Das ist der teuerste offene Punkt des Backlogs, und er kostet einen
Klick.

Der Inhalt von #441 ist gegengelesen und trägt: Reihenfolge 1 #440, 2 #429,
3 #434, 4 #430, 5 #436, 6 #427, 7 #438, mit den zwei harten Abhängigkeiten und
der Regel, dass ein neues `agent-ready`-Issue ohne Platz in der Liste als
unsichtbar gilt.

### 4.3 Wo stehen #427 und #436/#402 wirklich?

#441 setzt sie auf Platz 5 und 6, beide mit „Unabhängig" begründet. Das ist
sachlich richtig, aber es ist eine **Prioritäts-Entscheidung ohne Owner-Aussage**:
für #438 und #435 gibt es eine ausdrückliche Owner-Reihenfolge („nach dem
Cloud-Launch-Block"), für #427 und #436 nicht. Falls die Fehlercodes (#436/#402)
oder die Favoriten (#427) *vor* dem Launch-Block liegen sollen, ist das jetzt
zu sagen — beide sind file-disjunkt zur Launch-Spur (§6) und könnten parallel
laufen.

## 5. Vorschläge — nicht angelegt, weil Refinement keine Issues anlegt

Das Playbook *Issue-Refinement* verbessert bestehende Issues; das Anlegen läuft
über *GitHub-Artefakt anlegen & pflegen*. Beide Funde sind belegt und
schnittreif — sie brauchen nur ein „ja".

### 5.1 Drift-Wächter für `docs/reference/openapi.json` (`size/S`)

Fertig heißt: ein Test schlägt fehl, wenn die eingecheckte Spec von
`app.openapi()` abweicht — analog `test_openapi_contract.py`, das dasselbe
bereits für `openapi_surface.json` tut. Verifikation:
`uv run pytest apps/api/tests/test_openapi_contract.py -q`. Out: Änderungen am
Contract-Test selbst, an `export_openapi.py`, an der Spec.

### 5.2 Typecheck-Kommando in der Doku auf das CI-Kommando ziehen (`size/S`)

Fertig heißt: `CLAUDE.md:151`, `CLAUDE.md:233`, `CONTRIBUTING.md:79` und
`docs/CLAUDE-PROFILE.md:22` nennen `npx tsc -b` statt `npx tsc --noEmit`.
Verifikation: `grep -rn 'tsc --noEmit' CLAUDE.md CONTRIBUTING.md docs/` → 0
Treffer; `cd apps/web && npx tsc -b` → Exit 0. Out: die CI-Datei ändern, andere
Kommandos anfassen. Reiner Doku-PR — und damit zugleich der erste echte
Testfall für #440, wenn dieses vorher liegt.

### 5.3 Sammelpunkt-Regel gegen Merge-Konflikte (`size/S`, siehe §6.2)

### 5.4 #435 in W1/W2 schneiden

Das Issue sieht die Zerlegung selbst vor („nach Freigabe"). Zwei Pakete stehen
fertig im Body: **W1 GoTrue-Update** (Image ≥ v2.163.0 in beiden Compose-Dateien,
RP-Konfiguration, Doku, `compose-smoke` + E2E grün) und **W2 UI** (Passkey-Enroll
in `MfaSection`, Step-up-Auswahl, E2E mit Playwright Virtual Authenticator).
Vorbedingung bleibt der Breaking-Change-Check zwischen v2.158.1 und Zielversion,
den W1 als ersten Schritt trägt. Zuschnitt erst nach dem Cloud-Launch-Block —
so steht es in der Owner-Reihenfolge.

## 6. Gruppen: was können Agenten parallel abarbeiten?

Die Reihenfolge in #441 ist eine **Liste**, kein Parallelisierungs-Plan. Für
mehrere gleichzeitig laufende Sub-Agents zählt Datei-Disjunktheit. Grundlage
sind die `Scope In`-Listen der Issues.

### 6.1 Kollisions-Paare (dürfen NICHT gleichzeitig laufen)

| Paar | Gemeinsame Dateien | Folge |
|---|---|---|
| **#427 ↔ #436** | `apps/web/src/api/client.ts`, `docs/reference/openapi.json`, `apps/api/tests/contract/openapi_surface.json`, `i18n/locales/{de,en}.json` | Beide regenerieren die OpenAPI-Artefakte. Parallel bedeutet garantierter Konflikt in generierten Dateien — der teuerste Konflikttyp, weil er nur durch erneutes Regenerieren auflösbar ist. **Strikt sequenziell.** |
| **#429 ↔ #430** | `apps/web/src/config.ts` (+ Test), `apps/web/docker/40-who2be-runtime-config.sh`, `features/auth/pages/LoginPage.tsx`, `.env.example`, `deploy/hetzner/.env.example`, `i18n` Namespace `auth` | Beide erweitern dieselbe `RuntimeConfig` und dieselbe Login-Seite. **Strikt sequenziell.** |
| **#430 ↔ #435** | `LoginPage.tsx`, `MfaSection`-Umfeld, `i18n` `auth` | #435 liegt ohnehin nach #430. Reihenfolge einhalten. |

Die Reihenfolge aus #441 (2 #429 → 4 #430, 5 #436 → 6 #427) hält beide Paare
bereits auseinander. Das ist kein Zufall, aber es steht nirgends begründet —
wer die Liste umsortiert, muss die zwei Paare kennen.

### 6.2 Sammelpunkte — vier Dateien, die fast jedes Paket anfasst

| Datei | Betroffene Issues |
|---|---|
| `.claude/context/STATE.md` | #427 #428 #429 #430 #434 #435 #436 #438 #440 (9 von 12) |
| `CHANGELOG.md` | #427 #429 #430 #435 #436 #438 |
| `apps/web/src/i18n/locales/{de,en}.json` | #427 #429 #430 #435 #436 |
| `docs/reference/openapi.json` + `openapi_surface.json` | #402 #427 #436 #440 |

Bei parallelen Läufen kollidieren diese vier **immer**, auch zwischen sonst
disjunkten Paketen. Kein Issue erwähnt das. Zwei Gegenmaßnahmen, beide billig:
den Eintrag in diese Dateien als **letzten Commit** eines Pakets setzen (dann
ist der Konflikt ein Ein-Zeilen-Merge statt eines Rebases über den ganzen Diff),
und `i18n` je Paket auf **einen** Namespace beschränken (`agents` / `auth` /
`errors` — hält die JSON-Konflikte auf getrennte Objekte). Gehört als Regel in
`CONTRIBUTING.md` §DoD, nicht in jedes einzelne Issue (Norm: was projektweit
gilt, steht eine Ebene höher). → Vorschlag §5.3.

### 6.3 Wellen-Vorschlag bei mehreren parallelen Agenten

Hält die Owner-Reihenfolge ein und nutzt Disjunktheit, wo sie besteht.

**Welle 1 — drei Agenten parallel**
`#440` (nur `.github/workflows/ci.yml` + `CONTRIBUTING.md`) ·
`#434` (nur `.claude/plan/**`, read-only) ·
`#429` (Auth-Seiten, `config.ts`, `smoke.sh`, Env-Doku).
Vollständig disjunkt bis auf `STATE.md`. #440 zuerst mergen — ab dann kostet
jeder Doku-PR der Folge-Wellen gut eine Minute statt 7:42.

**Welle 2 — zwei Agenten parallel, nach Welle 1**
`#430` (braucht #429 gemerged, §6.1; Security-Review + ADR-0052 laut §3.1) ·
`#436` (API + `client.ts` + OpenAPI).
Überschneidung nur in `i18n` (`auth` vs. `errors`) und `CHANGELOG` — mit der
Regel aus §6.2 beherrschbar.

**Welle 3 — ein Agent**
`#427` (erst nach #436 wegen der OpenAPI-Artefakte).

**Welle 4 — nach dem Launch-Block, Owner-Vorgabe**
`#438`, danach der Schnitt von `#431` W1–W4; anschließend `#435` W1 → W2.

**Dauerhaft parallel, kein Agent**
`#338` (`human-only`): O2 Branch-Protection/Merge-Strategie/Description/Topics,
O3 CLA-Assistant. Beeinflusst #440 (Weiche 1 dort setzt voraus, dass GitHub
„skipped" bei Required Checks wie Erfolg wertet — erst mit O2 nachweisbar).

**Nach #434, nicht vorher:** der Zuschnitt von #428 WP-2 bis WP-5. Er hängt am
Inventar *und* an den beiden Weichen aus §4.1 — beides muss vorliegen.

## 7. Was dieser Lauf nicht getan hat

Kein Code geändert, kein Branch für ein Issue geöffnet, kein Issue geclaimt,
keine Issues angelegt (§5 sind Vorschläge), die zwei Weichen auf #428 nicht
entschieden, PR #441 nicht gemerged und nicht angefasst — er liegt auf einem
fremden Branch. Einziger Schreibzugriff auf GitHub: der korrigierte Body von
#430 (§3.1).

# STATE — Wo stehen wir (Snapshot, pro Run überschrieben)

_Stand: 2026-09-06 (27. Lauf — Agent-Favoriten, #427)_

## Agent-Favoriten stehen (2026-09-06, 27. Lauf, #427)

Jedes Workspace-Mitglied kann einen Agent per Stern als **persoenlichen**
Favoriten markieren; Favoriten stehen als eigene Gruppe oben auf der
Agents-Seite. Serverseitig pro User gespeichert (`agent_favorite`, Migration
0083), also ueberlebt der Zustand Reload und Geraetewechsel — zwei Mitglieder
desselben Workspace sehen unterschiedliche Sterne.

**Warum eine eigene Tabelle:** eine `is_pinned`-Spalte auf `agent` waere
workspace-weit gewesen (widerspricht „pro User"), `localStorage` haette den
Geraetewechsel nicht ueberlebt. `workspace_id` liegt denormalisiert auf der
Zeile, weil die RLS-Policy sie dort braucht und sonst joinen muesste. **Keinen
FK auf den User** — kein Schema referenziert den GoTrue-User; die Bereinigung
bei Konto-Loeschung haengt deshalb an einer expliziten Zeile in
`purge_account_data`, nicht an einem CASCADE.

Der Stern kommt im **selben** Batch-Roundtrip wie die uebrigen List-Pills
(`LEFT JOIN agent_favorite`) — ein zweiter Query haette das
Ein-Roundtrip-Versprechen von `_enrich` gebrochen. Setzen/Entfernen sind zwei
idempotente Sub-Resource-Routen (`PUT`/`DELETE .../agents/{id}/favorite`, je
204), bewusst kein Feld in `AgentUpdate`: der Favorit gehoert dem User, nicht
dem Agenten. Jedes Mitglied inkl. `viewer` darf markieren (ein Favorit ist ein
privates Datum, kein Workspace-Inhalt); agent-gebundene Tokens bekommen 403.

**Die Umgebung hat sich geaendert — das ist der wichtigere Teil dieses Laufs.**
Bis hierher lief in dieser Session **kein** Docker, deshalb wurden alle
Integrationstests still uebersprungen: `uv run pytest --cov` meldete
`1305 passed, 448 skipped, 63.08 %` — das 85-%-Gate war schlicht unerreichbar
und musste in jedem Python-Paket als „nicht verifiziert" offengelegt werden.
Postgres 16 laesst sich hier aber **ohne** Docker installieren (`apt`, plus
`pg_trgm` und `pgvector`); mit `DATABASE_URL` darauf laeuft die volle Suite:
**1838 passed, 0 skipped, Coverage 90.93 %**. Die fuenf neuen
Integrationstests pruefen damit wirklich gegen eine DB, nicht gegen Mocks.

**Nachweise:** `uv run ruff check .` / `ruff format --check .` / `mypy .` (456
Dateien) gruen; `WHO2BE_REQUIRE_DB=1 uv run pytest --cov --cov-fail-under=85`
→ **1838 passed, 90.93 %**; `npm run lint` (0 errors), `npx tsc -b`,
`npm run test:coverage` (**1110 Tests**, Branches 81.65 %), `npm run test:a11y`
(53), `npm run build`; i18n-Paritaet `agents` in beide Richtungen leer;
`openapi.json` + `openapi_surface.json` regeneriert mit **genau zwei** neuen
Routen.

**Zwei eigene Fehlgriffe, beide zurueckgenommen statt uebertuencht:** ein
skriptgesteuertes Re-Indent von `AgentsPage.tsx` hat die Datei syntaktisch
zerlegt; und `npx prettier --write` auf dieselbe Datei hat 500 Zeilen auf
Prettier-Defaults umformatiert — das Repo hat **keine** Prettier-Config und
benutzt Prettier nicht. Beide Male zurueckgesetzt und die Aenderung von Hand
gemacht (94 statt 318 geaenderte Zeilen).

## „Angemeldet bleiben" steht (2026-09-05, 26. Lauf, #430)

Die Login-Seite traegt eine standardmaessig **nicht** gesetzte Checkbox. Mit
Haken wandert genau diese Session von `sessionStorage` nach `localStorage` und
ueberlebt neuen Tab + Browser-Neustart bis zu einer absoluten Obergrenze
(`WHO2BE_SESSION_MAX_AGE_HOURS`, Runtime-Config, Default 12, Bereich 1-24,
fail-closed auf 12). Ohne Haken bleibt das heutige Tab-Verhalten unveraendert.
Plan `.claude/plan/2026-09-05-2255_login-remember-session.md`.

**Cross-Tab-Logout war nicht zu bauen, sondern zu belegen.** `@supabase/auth-js`
eroeffnet den `BroadcastChannel` bereits, sobald `persistSession` und
`storageKey` gesetzt sind — beides gilt seit ADR-0035 unveraendert. Kein
eigener Listener, kein eigener Kanal; `lib/supabase.test.ts` haelt die
Vorbedingung fest, damit sie nicht unbemerkt wegkonfiguriert wird.

**Der Security-Review (Pflicht laut Weiche 8) war der eigentliche Ertrag.** Er
fand vier Wege, auf denen die Obergrenze — also genau das Argument, mit dem
ADR-0052 die Lockerung von ADR-0035 rechtfertigt — wirkungslos blieb:

1. Ein Login ohne Haken nach einem Login mit Haken liess den alten
   Refresh-Token im `localStorage` liegen. Weil der Marker dabei verschwand,
   fiel dieser Token zugleich aus der Ablaufpruefung — eine Datenleiche, die
   **nie** abgelaufen waere.
2. Marker und Zeitstempel standen in zwei Keys. Fehlte oder zerbrach der
   zweite, galt die Session als unbegrenzt: ein `setItem` aus den DevTools
   genuegte, um die Kappung dauerhaft abzuschalten (fail-open).
3. `bootstrap()` und der `onAuthStateChange`-Handler teilen sich `apply()`. Ein
   Lauf, der im Netzwerk-`fetchMe` haengt, konnte nach einem bereits erfolgten
   Ablauf-Logout die Session zurueckschreiben und den Logout zuruecknehmen.
4. „Ueberall abmelden" und die Account-Loeschung rufen `supabase.auth.signOut`
   direkt auf; der Marker blieb stehen und der naechste Login ohne Checkbox
   (OAuth, Magic-Link) landete ungefragt auf der Platte.

Alle vier sind behoben: EIN atomarer Marker, der ohne lesbaren Zeitstempel als
**abgelaufen** gilt (fail-closed statt fail-open); die Ablaufpruefung sitzt in
`apply()` statt nur in `bootstrap()` und ist durch einen Generationszaehler
gegen Ueberholmanoever geschuetzt; jeder Moduswechsel raeumt den Session-Blob
des unzustaendigen Backends ab; ein zentraler `SIGNED_OUT`-Handler loescht den
Marker unabhaengig von der Quelle. Der gesamte Marker-Zustand liegt jetzt in
`apps/web/src/lib/remember-session.ts` — die vorherige Verdopplung der
Key-Literale ueber zwei Dateien war die Ursache dafuer, dass drei der vier
Befunde ueberhaupt entstehen konnten.

**Nachweise:** `npm run lint` (0 errors), `npx tsc -b`, `npm run test:coverage`
(188 Dateien, **1103 Tests gruen**; Statements 87.00 / Branches 81.63 /
Functions 82.60 / Lines 88.03 — alle ueber den Schwellen 80/79/75/80),
`npm run test:a11y` (53 gruen), `npm run build`, i18n-Paritaet `auth` in beide
Richtungen leer. **Nicht verifiziert:** die beiden E2E-Journeys — in dieser
Umgebung laeuft kein Docker, sie sind nur typgeprueft. Der CI-Job `e2e` faehrt sie.

**Bewusst offen gelassen (als Folge-Issues erfasst, nicht still gefixt):**

- Der Marker ist ein **globaler** Schalter im `localStorage`, kein Per-Tab-
  Zustand. Ein Login in Tab B aendert das Storage-Routing eines parallel
  laufenden Tab A. Eine Bindung des Markers an die Session-Identitaet ist ein
  eigenes Paket.
- `WHO2BE_SESSION_MAX_AGE_HOURS` ist in **keinem** Compose-`web`-Service
  durchgereicht — der Entrypoint liest die Variable, aber kein Stack setzt sie.
  Ein Betreiber, der auf 1 h haerten will, bekommt still 12 h. Weiche 7 des
  Issues schliesst einen Compose-Diff in diesem Paket aus; beide
  `.env.example` benennen die fehlende Verdrahtung.
- Ein Befund **ausserhalb** des Pakets (`apps/api`, aal2-Gate bei der
  API-Token-Ausstellung) ist getrennt gemeldet — nicht Teil dieser ADR.

## Responsive-Fundament steht (2026-09-05, 25. Lauf, #438)

W0 von #431, erstes Paket nach dem Cloud-Launch-Block. Drei Bausteine, auf denen
W1 bis W4 aufsetzen: Abschnitt „Responsive & Breakpoints" in
`docs/frontend/design-language.md` (Skala, Zielviewports, Mobile-first-Regel,
Prefix-Pflicht, 6-Punkte-Review-Checkliste, verlinkt aus §12 und §13),
`hooks/useMediaQuery.ts` mit `useMediaQuery`/`useIsMobile`, und
`components/ui/sheet.tsx` auf Radix Dialog. Plan
`.claude/plan/2026-09-05-2220_responsive-fundament.md`.

**Das Paket aendert bewusst kein sichtbares Verhalten.** Kein Konsument wurde
umgestellt — das ist W1. `git status` zeigt ausser den fuenf neuen Dateien nur
`components/ui/index.ts`, `design-language.md` und `CHANGELOG.md`; die Hauptgefahr
war nicht ein Fehler, sondern Scope-Creep Richtung `AppShell`.

Der matchMedia-Guard ist strukturgleich zu `app/ThemeProvider.tsx:22-23`
uebernommen (`typeof window.matchMedia !== 'function'` ⇒ `false`), damit es im
Repo genau ein Muster dafuer gibt und nicht zwei.

**Nebenfund #465 (vorbestehend, groesser als gedacht):** `tailwindcss-animate`
steht in `package.json:48`, ist aber nie geladen — Tailwind v4 braucht
`@plugin` in `globals.css`, und das Repo hat bewusst keine `tailwind.config.*`.
**Fuenf** Primitives (`dialog`, `dropdown-menu`, `popover`, `info-tooltip` und
jetzt `sheet`) tragen damit Animations-Klassen, die kein CSS erzeugen. Tailwind
ignoriert unbekannte Klassen stillschweigend: kein Build-, Lint- oder
Testfehler. Nicht in #438 gefixt, weil die vier anderen Primitives ausserhalb
des Scopes lagen.

**Verifikation:** lint 0 Errors · `tsc -b` Exit 0 · **1063 Tests gruen**
(Baseline 1043, +20 exakt die neuen) · Coverage 86,76 / 81,44 / 82,34 / 87,78
(Baseline 86,69 / 81,36 / 82,27 / 87,71, Floors 80/79/75/80) · a11y 53 passed ·
Build gruen.

## Generischer Billing-Webhook gehaertet (2026-09-05, 24. Lauf, #452)

WP-5 von #428. **Der Befund war vor der Umsetzung als nicht ausnutzbar
eingestuft** und ist es weiterhin: kein Anbieter sendet auf diesen Pfad (das
Repo haengt allein an `mollie-api-python`, Mollie signiert nicht und laeuft
ueber den eigenen, bereits geschuetzten Pfad), und ohne gesetztes
`billing_webhook_secret` antwortete der Endpunkt ohnehin mit 400. Vorsorge fuer
den Tag, an dem ein signierender Anbieter dazukommt. Plan
`.claude/plan/2026-09-05-2130_webhook-haertung.md`.

Vier von fuenf Massnahmen umgesetzt, in der Reihenfolge absteigender Wirkung:

1. **Ablauffrist** — ein Grant ohne Periodenangabe wird abgewiesen
   (`WebhookError`) statt unbefristet geschrieben. Zurueckweisen statt Deckeln:
   kein zu rechtfertigender Ersatzwert, und es entsteht ueberhaupt kein
   Schreibvorgang. Ein Entitlement ohne Ablauf darf ausschliesslich aus dem
   OSS-/On-Prem-Default stammen (`licensing/entitlement.py:110`).
2. **Dedupe** — Claim ueber die **Envelope**-Event-ID (nicht die Objekt-ID, die
   in mehreren Ereignissen vorkommt) vor dem Upsert, Release bei Fehler danach.
   Vorlage war der Mollie-Pfad, **ohne** gemeinsame Abstraktion: eine Basisklasse
   fuer zwei Faelle waere nicht belegt.
3. **Zeitfenster** — der generische HMAC-Zweig hat, anders als der
   Stripe-Zweig, keinen Zeitstempel im Header. Geloest ueber das `created`-Feld
   des **HMAC-gedeckten** Payloads; das Header-Format bleibt unangetastet, weil
   es ein Vertrag mit einem Anbieter waere, den es nicht gibt. Fehlt die Zeit:
   fail closed.
4. **Mount nur mit Secret** — ohne `billing_webhook_secret` existiert die Route
   nicht mehr (404 statt 400).

**Monotonie (AC 5) bewusst geschnitten**, Weiche 4 erlaubt das nach der zweiten
Massnahme. `org_entitlement.updated_at` ist die Schreibzeit, nicht die
Ereigniszeit des Anbieters — ein Vergleich dagegen ist in die falsche Richtung
unsicher und wuerde ein legitimes, spaet zugestelltes Ereignis abweisen. Weiche
6 schliesst eine Migration fuer dieses Paket aus. Als **#462** dokumentiert, mit
drei Wegen und der Empfehlung, es bis zur Anbindung eines zweiten Anbieters
offen zu lassen. `entitlement_repository.py` blieb unveraendert.

**Der Security-Review hat einen Fehler in der Vorgabe gefunden — nicht in der
Umsetzung.** Die Leitplanke „zieh die Frische aus dem `created`-Feld des
signierten Bodys" traegt nicht: weil der Wert HMAC-gedeckt ist, kann ein
Anbieter ihn bei einer Wiederzustellung **nicht neu stempeln**. Mit einem
5-Minuten-Fenster waere jeder spaetere Retry dauerhaft an der Signaturpruefung
gescheitert — und damit die Claim-Freigabe aus Massnahme 2 ein Versprechen ohne
Deckung gewesen. Die gefaehrliche Richtung ist der **verlorene Revoke**: eine
Kuendigung waere nie angewendet worden, der Zugriff geblieben. Die Haertung
haette ein Loch gerissen, waehrend sie eines schliesst.

Geloest durch Entkopplung der beiden Begriffe: der **Dedupe-Ledger ist der
Replay-Schutz**, das Zeitfenster nur eine Plausibilitaetsschranke. Der
generische Zweig bekommt dafuer eine eigene Konstante
(`_GENERIC_EVENT_MAX_AGE_SECONDS`, 7 Tage), waehrend
`_SIGNATURE_TOLERANCE_SECONDS` (5 Min) fuer den Stripe-Zweig richtig bleibt —
dort ist `t=` ein Header-Wert, den der Absender pro Zustellung neu stempelt.
Beide Konstanten tragen den Grund ihres Unterschieds als Kommentar.

Drei weitere Befunde behoben: **Plausibilitaetsband** fuer das Periodenende
(`_MAX_PERIOD_HORIZON`, ~13 Monate — Massnahme 1 erzwang bis dahin nur die
*Existenz* eines Ablaufs, nicht seine Plausibilitaet: `expires_at` im Jahr 9999
war faktisch unbefristet); ein gemeinsamer `_coerce_int`-Helfer gegen
durchschlagende Ausnahmen bei missgebildeten Zahlenfeldern (500 statt
fail-closed 400 — auf einem Webhook heisst 500 „bitte erneut zustellen");
Hex-Validierung (`_HEX64_RE`) vor jedem `compare_digest`, weil ein
Nicht-ASCII-Header sonst einen unauthentifizierten 500 samt Stacktrace erzeugt.

**Fuenf Restbefunde als #463** (NIEDRIG, keine Regression): Konfigurations-Orakel
durch 404-vs-400, `include_routers` ignoriert injizierte Settings,
Dedupe-Namensraum nicht anbieterspezifisch, fehlende Sicherheitsprotokollierung,
und derselbe Konversionsfehler im vorbestehenden `_parse_stripe_header`.

**Verifikation:** 80 Billing-Tests gruen (Baseline 59) · ruff, format und mypy
sauber · `git diff -- mollie.py` leer · keine Migration.

**Nebenbefund am eigenen Werkzeug:** `ruff format` prueft Python-Code-Bloecke
**in Markdown** mit. Ein zitiertes einzeiliges `if` in der Plan-Datei haette die
CI rot gemacht. Kuenftige Plaene: zitierten Python-Code formatiert halten oder
den Block nicht als `python` auszeichnen.

## Tarife bewerben das Kontingent statt Feature-Codes (2026-09-05, 23. Lauf, #449)

WP-2 von #428. Das Billing-Panel warb mit `composite_playbooks`, `agents` und
`audit_export` — Funktionen, die Free ebenfalls hat: repo-weit gatet keine
Stelle mit `has_feature()`, und fuer `audit_export` existiert nicht einmal ein
Endpunkt. Jetzt beschreiben Doku und Panel die vier Groessen, die der Code
durchsetzt: Preis, MCP/Monat, MCP/min, Entity-Limit. Plan
`.claude/plan/2026-09-05-2045_tarife-kontingent.md`.

**Muster-Entscheidung: Tarif-Liste als Datensatz** (`TIERS` im Billing-Feature)
statt zweier fester `if isPro`-Zweige. Beleg fuer die Variabilitaet: das Backend
fuehrt die Mehrzahl bereits als Struktur (`PAID_PLANS` als Dict ueber Codes,
`plans.py:92`). Ein dritter Tarif ist damit ein Eintrag, kein Umbau. Die Liste
dupliziert Preis und Entity-Limit aus dem Backend — bewusst, mit Quellenverweis
an der Konstante, weil `EntitlementInfo` beides nicht ausliefert.

**Zwei Befunde am Issue:**

1. **Weiche 3 nennt einen Plan-Code, den es nicht gibt.** `EntitlementInfo`
   (`apps/web/src/api/types.ts:980-988`) traegt `mcp_monthly_quota` und
   `mcp_rate_per_min`, aber **keinen** `plan_code` — `META_PLAN_CODE` lebt nur
   in den Mollie-Metadaten. Kein Blocker, die Quota reicht.
2. **Die Feature-Codes sind NICHT wirkungslos.** AC 1 erlaubte den Vermerk, sie
   seien „Metadaten ohne Leistungsversprechen". `Entitlement.entity_limit()`
   leitet aber genau aus ihnen ab (`paid_features = features - {CORE}` ⇒
   unbegrenzt statt 50, `entitlement.py:105-107`). Wirksam ist, **ob** ein
   Paid-Code vorliegt; nicht wirksam ist, **welcher**. Die Doku sagt jetzt das,
   statt eine Unwahrheit durch die naechste zu ersetzen.

**Eine Regression im ersten Wurf abgefangen.** Der Sub-Agent hatte die
Tarif-Erkennung als exakten Quota-Match gebaut (`quota === 1_000 | 100_000`) und
den Fall selbst nur als Randnotiz gemeldet: ein `manual_override`-Entitlement
mit individueller Quota waere damit auf „nicht bezahlt" gefallen und haette den
Upgrade-CTA gezeigt — schlechter als der alte Feature-Array-Code, und
`manual_override` ist eine der vier benannten Entitlement-Quellen (CLAUDE.md).
Nachgebessert: **zwei getrennte Fragen**. „Ist bezahlt?" ist ein Schwellwert
(alles ueber der Free-Quota, `null` = unbegrenzt zaehlt mit) und steuert den
CTA; „welcher Tarif?" bleibt exakter Match und steuert nur Name/Preis/
Entity-Limit, ohne Treffer `panel.plan.unknown`. Ein Test haelt den Fall fest.

**Verifikation:** lint 0 Errors · `tsc -b` Exit 0 · 1043 Tests gruen (Baseline
1042) · Coverage 86,69 / 81,36 / 82,27 / 87,71 (Floors 80/79/75/80, Baseline
86,52 / 81,12 / 82,05 / 87,55) · Build gruen · Panel-Suite 10 gruen.

## Kettentest belegt: bezahltes Abo schaltet das Limit frei (2026-09-05, 22. Lauf, #451)

WP-4 von #428. Die gravierendste Luecke des Cloud-Inventars geschlossen: Checkout,
Webhook, Entitlement-Schreibpfad und Limit waren je einzeln geprueft, dass ein
bezahltes Abo am Ende wirklich hoehere Limits freischaltet, war **nirgends**
belegt. Plan `.claude/plan/2026-09-05-2000_billing-kettentest.md`, Umsetzung ueber
einen Sonnet-Sub-Agent.

Neu: `packages/billing/tests/test_checkout_webhook_entitlement_limit_chain.py`
(Positivfall + Gegenfall), ein HTTP-Erfolgspfad fuer den Checkout in
`test_mollie_endpoint.py`, und Check 7 in `scripts/smoke.sh`. **Kein
Produktivcode angefasst** (`git diff --stat -- packages/billing/src apps/api/src`
leer) — so verlangt es das Issue: der Test erbringt Beweise, er repariert nicht.

**Die Gegenprobe ist der eigentliche Beleg.** Nimmt man den Webhook-Aufruf und
seine Folge-Assertions aus dem Test, scheitert er nicht an einer kuenstlichen
Zusicherung, sondern mit `429 Token-Ratenlimit ueberschritten` in
`services/mcp_limit_service.py:90` — also im echten Produktivcode. Datei danach
byte-identisch wiederhergestellt (`diff` leer), Suite wieder 59 gruen.

**Zwei Befunde am Issue selbst:**

1. **Weiche 4 war sachlich falsch.** Sie schlug den Entitlement-Lese-Pfad fuer
   den Smoke-Check vor, „weil er die Editions-Frage genauso beantwortet". Tut er
   nicht: `entitlement.router` wird in `main.py:391` **unconditional**
   registriert, waehrend `_register_billing_if_present` (`:407`) nur die
   Schreibrouten bindet — der Lese-Pfad existiert in beiden Editionen und
   liefert nie 404. Stattdessen prueft Check 7 `POST /v1/billing/webhook`
   (gegated), das ohne Signatur fail-closed 400 liefert und damit weder Mollie
   noch DB beruehrt (AC 5 gewahrt).
2. **Umgebungsgrenze, gemessen:** ohne Docker faellt die volle Suite auf
   63,08 % Coverage (1305 passed, 448 skipped) — `--cov-fail-under=85` ist hier
   fuer **jedes** Python-Paket unerreichbar, nicht nur fuer dieses. Deshalb
   traegt der Kettentest bewusst keinen `integration`-Marker: er waere sonst nie
   ein einziges Mal gelaufen. Der SQL-Schreibpfad in `org_entitlement` bleibt
   damit ausserhalb dieses Belegs (er hat eigene Integrationstests).

## „Coming soon"-Modus steht (2026-09-05, 21. Lauf, #429, PR #457)

Erstes Paket der Warteschlange nach der Aufbereitung; harte Vorbedingung fuer
#454. `WHO2BE_LAUNCH_MODE=open|coming_soon` (Default `open`) schaltet `/signup`
auf eine Hinweisseite, waehrend Login, Passwort-Reset, Einladungen und
`/oauth/consent` unveraendert laufen. Der Wert kommt ausschliesslich aus
`/config.js` — Umschalten braucht keinen Rebuild. Plan + Uebergabe-Bericht:
`.claude/plan/2026-09-05-1849_launch-mode-coming-soon.md`.

**Zuschnitt-Luecke, die erst die Konsolidierung fand:** beide Compose-Dateien
reichten die neue Variable nicht an den `web`-Container durch
(`docker-compose.yml:184` und `deploy/hetzner/who2be/docker-compose.yml:143`
tun das fuer `WHO2BE_SIGNUP_DISABLED` seit jeher). `/config.js` haette immer
`launchMode: "open"` geschrieben — das Feature waere im echten Stack wirkungslos
gewesen, bei gruenen Tests. Die Scope-Liste des Issues nannte jeden Konsumenten
der Variablen, aber nicht ihren Transportweg. Vom Orchestrator nachgezogen.

**Verifikation (selbst gefahren):** lint 0 Errors, `tsc -b` sauber, 1038 Tests
gruen, a11y 48 gruen, Build gruen; Coverage 86.52 / 81.12 / 82.05 / 87.55 gegen
80 / 79 / 75 / 80. Dazu die Wahrheitstabelle des Entrypoints ueber alle sechs
Env-Kombinationen — Shell-Logik faellt sonst durch jedes Unit-Test-Raster.

**Offen (nicht automatisiert belegbar):** Akzeptanzkriterium 1 und 4 gegen einen
laufenden Compose-Stack (Browser + `curl` gegen `/auth/v1/signup`, `smoke.sh` in
beiden Modi) — im Uebergabe-Bericht als Rest-Test-Liste gefuehrt.


## Cloud-Deploy zieht das CI-Image aus der Registry (2026-09-05, 20. Lauf, #450)

Erstes Paket der Warteschlange, das dieser Lauf abgearbeitet hat (#429 lag bei
einer parallelen Session). WP-3 von #428. Umsetzung ueber einen Sonnet-Sub-Agent
(klar umrissenes Paket, fuenf Weichen im Issue entschieden), Plan-Datei
`.claude/plan/2026-09-05-1930_cloud-registry-pull.md`.

`api` und `migrate` ziehen jetzt `ghcr.io/luetzey/who2be-api-cloud:${API_IMAGE_TAG}`
statt auf der Prod-Box zu bauen; `deploy.sh` pullt im Cloud-Zweig `api migrate web`
(vorher nur `web`); `RUNBOOK.md` traegt die Sektion „Notfallpfad: Registry nicht
erreichbar" mit Handkommandos.

**Zwei Befunde am Issue selbst, beide belegt:**

1. **Ein Verifikations-Kommando war unerfuellbar.** Das Issue verlangte
   `grep -c 'pull_policy: build'` → 0, seine eigenen Kriterien nennen aber nur
   `api` und `migrate`. Das dritte Vorkommen gehoert `web` — und `web` kann
   nicht auf Pull umgestellt werden: die Build-Matrix
   (`.github/workflows/deploy.yml:17-44`) baut `api`, `web`, `mcp`, `api-cloud`,
   aber **kein** `web-cloud`, und die Billing-UI wird zur Compile-Zeit
   tree-geshaked (ADR-0029). Richtiger Wert ist 1.
2. **AC 5 ist funktional, nicht woertlich erfuellt.** Es verlangt das
   Registry-Image „statt eines Build-Kontexts"; der `build:`-Block bleibt bei
   `api`/`migrate` stehen, weil der Runbook-Notfallpfad
   (`docker compose build api migrate`) sonst die On-Prem-Stage ohne Billing
   baute. Entscheidend ist, dass `pull_policy: build` weg ist — der Regelweg ist
   damit der Pull. Ein stiller Lokal-Build bei Registry-Ausfall ist
   ausgeschlossen, weil `deploy.sh:30` `set -euo pipefail` faehrt und der
   explizite `pull`-Schritt den Lauf abbricht (Weiche 3 des Issues gewahrt).

**Nebenfund, eigenes Issue:** `deploy/hetzner/.env.example` fehlt
`MINIO_ROOT_PASSWORD`, das `docker-compose.yml:93` zwingend fordert (`:?`).
`docker compose config` gegen diese Vorlage scheitert deshalb — unabhaengig von
#450, aber es macht AC 5 in der gegebenen Form unpruefbar. Verifiziert wurde mit
der Variable als Shell-Env, ohne die Datei zu aendern.

## Backlog aufbereitet, #438 vorgezogen (2026-09-05, 19. Lauf — nur GitHub + Doku)

Alle acht offenen Issues ohne `agent-ready` gegen die Norm geprueft. Ergebnis:
**kein einziges wurde neu startbar** — und das ist der richtige Befund, nicht
ein zu duenner Lauf. Zwei sind `human-only` (#454, #338), eines ist das
Queue-Issue selbst (#442), vier sind `size/M`-Tracking (#428, #402, #431,
#435) und werden nach der Norm durch Zuschnitt startbar, nicht durch
Nachtragen von Feldern; #436 haengt an einer offenen Architektur-Weiche.

**Ein Beleg-Fehler in #435 korrigiert (Body ersetzt, Original archiviert).**
Der GoTrue-Pin steht an drei Stellen, nicht an zwei: `docker-compose.yml:50`,
`deploy/hetzner/supabase/docker-compose.yml:63` und
`deploy/dokploy/docker-compose.yml:81`. Ist-Zustand, W1-Text, Scope-In-Liste
und AC 1 nannten uebereinstimmend nur zwei. Ein Agent haette W1 danach
geschnitten und die dritte stehen lassen — und weil `dokploy` in `.github/`
und `scripts/` nicht vorkommt, meldet das kein Check, nur der Review. Das
Issue traegt jetzt eine fuenfte vorentschiedene Weiche mit der uebertragbaren
Regel: wer einen Image-Pin hebt, hebt alle Vorkommen oder begruendet die
Abweichung im PR.

**#438 von Platz 10 auf Platz 7.** Die Owner-Vorgabe lautet „nach dem
Cloud-Launch-Block" — sie bindet #438 an den Block, nicht ans Listenende.
#430 und #427 gehoeren nicht zum Block, sind Flaeche und oeffnen nichts;
#438 ist Fundament und oeffnet #431 W1-W4. Datei-disjunkt zu beiden geprueft
(`components/ui/sheet.tsx` + `@/hooks` + Design-Sprache gegen `config.ts`/
`LoginPage.tsx` bzw. OpenAPI-Artefakte). Die Gegenlesart steht als
Rueckfallregel im Queue-Issue — sie ist vertretbar, nur nicht die, die aus
den fuenf Kriterien folgt.

**PROJECT.md §Reihenfolge war gedriftet:** die Tabelle listete #440/#434 als
offen und kannte die sechs Kinder von #428 nicht. Da die Arbeitsteilung
„Queue-Issue traegt die Reihenfolge, PROJECT.md die Begruendung" lautet, war
genau die Quelle veraltet, die den Widerspruchsfall aufloest. Zusaetzlich
zeigte AC 1 auf „#428 WP-4"; der reale Deploy ist seit der Zerlegung #454
(WP-7), WP-4 ist der Kettentest.

**Offen und blockierend: #436.** Zwei maschinenlesbare Fehler-Vokabulare
nebeneinander (`ApiProblem.reason` vs. neuer `ErrorCode`) — Owner-Weiche,
drei Optionen stehen als Kommentar am Issue. Solange sie offen ist, hat #402
keine startbare Welle.

**Neue Pflege-Regel 9 im Queue-Issue:** eine Position, die nicht aus den fuenf
Kriterien folgt, gehoert in den Praeferenz-Abschnitt. Wer sie dort nicht
notiert, macht ein Urteil zu einer scheinbaren Ableitung.

**Zwei Laeufe parallel — hier zusammengefuehrt.** Der 18. Lauf (unten, Session
`012vSCkGuUtrf5TkckHUoU4i`, PR #455) und dieser hier haben denselben Auftrag
unabhaengig bearbeitet und beide `.github/PROJECT.md` §Reihenfolge sowie diesen
Snapshot angefasst — beide sauber gegen `main`, aber garantiert kollidierend
beim zweiten Merge. Statt das dem Zweitmerger zu ueberlassen, ist der Branch
von #455 hier hineingemergt: die Reihenfolge-Tabelle stammt aus diesem Lauf
(sie traegt #438 auf Platz 7 und die Praeferenz-Ausweisung), die Zusaetze des
18. Laufs (Disjunktheits-Hinweis #450, ADR-0035/0052 bei #430, Zeilennummern
der GoTrue-Pins) sind uebernommen. **#455 kann damit geschlossen werden**, ohne
dass Inhalt verloren geht. Beide Laeufe haben die drei GoTrue-Pin-Stellen
unabhaengig voneinander gefunden — der Befund ist damit doppelt belegt.

## Backlog gegen die Norm geprueft, #436 blockiert (2026-09-05, 18. Lauf)

Vollstaendiger Vorbereitungslauf ueber alle offenen Issues; Plan-Datei
`.claude/plan/2026-09-05-1625_backlog-vorbereitungslauf.md`. Audit ueber drei
parallele Sub-Agents (Sonnet), jeder uebernommene Befund vor dem Schreiben
selbst am Repo nachgeprueft; eine gemeldete „offene Weiche" (#429 ↔ #430)
verworfen, weil #442 sie laengst traegt.

**Zehn von zwoelf Issues erfuellen die Norm ohne Abstriche.** Der eine Fund mit
Substanz: **#436** plant `packages/models/src/who2be_models/errors.py` als
Neuanlage, obwohl die Datei seit WP-2/#254 existiert und mit `ApiProblem.reason`
bereits einen stabilen maschinenlesbaren Fehlerschluessel traegt
(`packages/models/src/who2be_models/__init__.py:29`). Dahinter steht die
unbeantwortete Frage, ob Who2Be zwei Fehler-Vokabulare nebeneinander bekommt —
gehoert in ADR-0051, also in genau das Dokument, das #436 schreiben soll.
`agent-ready` abgenommen, `needs-decision` gesetzt, drei Optionen als Kommentar.
Folge: **#402 hat derzeit keine startbare Welle.**

**Vier falsche Zeiger korrigiert** (je selbst verifiziert): #450 greppte in der
Verifikation auf `später`, die Datei ist durchgehend ASCII
(`grep -c '[äöüÄÖÜß]' deploy/hetzner/README.md` → 0) — ein Kriterium, das nichts
prueft; #453 `playwright.config.ts:23` → `:27`; #429 `.env.example:262-273` →
`:266-273` (zwei Stellen); #430 `LoginPage.tsx:25-50` → `:83-128, 208-269`.

**Reihenfolge:** #434 abgehakt (PR #448 gemergt), #427 vor das blockierte #436
gezogen (Rueckfallregel im Queue-Issue notiert), Wellen neu geschnitten,
`.github/PROJECT.md` §Reihenfolge kannte #449 bis #454 noch nicht — nachgezogen.

**Offen beim Owner:** Weiche auf #436; PR #443 (Draft des Vorlaufs) ist
inhaltlich ueberholt und kann geschlossen werden; zwei belegte Funde ohne Issue
(Typecheck-Drift `tsc -b` vs. `tsc --noEmit` an elf Doku-Stellen, bekannt als
FE-9 seit Juli; kein Drift-Waechter fuer `docs/reference/openapi.json`).


## Cloud-Launch-Readiness-Inventar liegt vor (2026-09-05, 17. Lauf, #434)

Zweites Paket der Backlog-Warteschlange (#442) und WP-1 von #428. Read-only Walk
ueber den kompletten Cloud-Pfad, Ergebnis als belegte Checkliste mit 58 Stationen
in `.claude/plan/2026-09-05-1520_cloud-launch-readiness-inventar.md`. Recherche
ueber vier parallele Explore-Subagents (Billing, Durchsetzung, Deploy/Web,
Vorgaenger-Dokumente), Sicherheitsfrage separat ueber `security-reviewer`.

**Zwei Annahmen aus #428/#434 korrigiert.** Erstens greift `FREE_ENTITY_QUOTA`
sehr wohl: `enforce_entity_quota` haengt an sechs Create-Endpunkten
(`routers/personas.py:101`, `agents.py:104`, `resources.py:96` u. a.) und wirkt
— anders als das Request-Limit — auch fuer Web-UI-Sessions, weil
`services/entity_quota_service.py:71` keinen `is_api_token`-Check hat. Zweitens
ist Pro nicht unbegrenzt, sondern 100.000/Monat + 240/min (`plans.py:74`); `None`
gilt nur fuer OSS/On-Prem. Die Quota-Zahlen in `docs/licensing/plans.md` stimmen
1:1 mit dem Code.

**Feature-Codes sind hohler als bekannt.** Repo-weit ruft keine Stelle
`has_feature()` als Gate auf; fuer `audit_export` existiert nicht einmal ein
Endpunkt — der einzige Export (`routers/gdpr.py:30`) ist fuer alle Tarife offen.

**Entwarnung Stripe-Header:** `verify_webhook_signature` laeuft ausschliesslich
im generischen Webhook (`router.py:161`), nie im Mollie-Pfad; dieser verifiziert
korrekt per `payments.get()`-Pull (`mollie.py:320`).

**Neuer Befund (Haertung, nicht ausnutzbar):** der generische Endpunkt
`/v1/billing/webhook` ruft den Dedupe-Ledger nicht auf. Geprueft nach
`SECURITY.md`: kein Anbieter sendet dorthin, und ohne gesetztes
`billing_webhook_secret` (Default leer, `core/config.py:191`) antwortet er 400.
Massnahmen in WP-4 des Zuschnitt-Vorschlags aufgenommen.

**Owner-Weichen entschieden (beide `needs-decision` auf #428):** Gating laeuft
ueber Quota statt Feature-Gates, Request-Limit bleibt auf API-Token beschraenkt,
`plans.md` + `BillingPanel` werden auf das Quota-Modell umgestellt (WP-2);
Cloud-Image-Deploy per Registry-Pull mit Host-Build als Runbook-Notfallpfad.
Wichtig fuer die Planung: Registry-Pull ist fuer die Cloud-API **nicht**
implementiert — `deploy/hetzner/who2be/docker-compose.cloud.yml:41` steht auf
`pull_policy: build`. Die Entscheidung ist damit Umbauarbeit (WP-3), nicht nur
ein Runbook-Abschnitt.

Verifikation: die sieben Kommandos aus #434 laufen gruen (109 Tabellenzeilen,
kein fremder Status, jede `fertig`-Zeile belegt, Negativ-Liste leer). Kein Code
angefasst — Diff ist Plan-Datei + README-Zeile + dieser Eintrag.

## CI ueberspringt die schweren Jobs bei reinen Doku-PRs (2026-09-05, 16. Lauf, #440)

Erstes Paket der Backlog-Warteschlange (#442). `ci.yml` hatte keinen
Pfadfilter: eine Aenderung an zwei Markdown-Dateien fuhr Postgres,
Compose-Stack und Playwright — 7:42 fuer einen Apparat, der daran nichts
pruefen kann. Zehn der letzten zwanzig Commits sind reine Doku-/Memory-Commits,
weil jeder Agenten-Lauf STATE.md fortschreibt.

Neuer Job `changes` klassifiziert den PR-Diff per `git diff` (keine
Fremd-Action, derselbe Checkout-Pin wie die uebrigen fuenf Stellen);
`python`, `web`, `compose-smoke` und `e2e` haengen per `needs:`/`if:` daran.
`audit` und CodeQL laufen immer. Begruendung der Gate-Job-Form statt
`paths-ignore`: siehe DECISIONS 2026-09-05.

Verifikation: YAML parst, Gating aus dem geparsten YAML gegengelesen,
Klassifikation gegen sieben Faelle durchgespielt (inkl. gemischt und
`nur ci.yml` — der Gate kann sich nicht selbst stilllegen). **Diff-Coverage
ist hier nicht anwendbar** (kein Test fuehrt `ci.yml` aus); der Nachweis sind
vier Beleg-Runs am PR. Plan + Uebergabe-Bericht:
`.claude/plan/2026-09-05-1305_ci-doku-gate.md`.


## Backlog gegen die Norm geprueft, Tabelle angeglichen (2026-09-05, 15. Lauf)

Auftrag: jedes offene Issue ohne `agent-ready` startbar machen, dann die Queue
neu ordnen. **Ergebnis: kein einziges Issue durfte `agent-ready` bekommen** —
und das ist der richtige Zustand, kein Versaeumnis.

- **#428, #402, #431, #435** sind inhaltlich vollstaendig veredelt (Ist-Zustand
  mit datei:zeile-Belegen, vorentschiedene Weichen, Acceptance, Out-of-Scope,
  exakte Verifikations-Kommandos), aber `size/M`. Nach der Norm
  „Agent-ready Arbeitspaket" wird so etwas **nicht durch Nachtragen von Feldern**
  startbar, sondern durch Zuschnitt. #428/#402/#431 haben ihr naechstes Kind
  bereits herausgeloest (#434/#436/#438); **#435 als einziges noch nicht.**
- **#338** traegt `human-only` (Refinement endet dort per Playbook-Schritt 1),
  **#442** ist die Queue selbst, kein Arbeitspaket.
- Die sieben `agent-ready`-Issues wurden gegen die vier Pflichtfelder
  gegengeprueft — alle sieben tragen sie vollstaendig, inkl. Vorentschieden und
  Eskalation. Keine Nachbesserung noetig.

Reihenfolge unabhaengig gegen die fuenf Kriterien neu hergeleitet; sie kommt
identisch zur Fassung von 12:41 heraus (#440, #434, #429, #436, #430, #427,
#438), deshalb **keine Umsortierung**. Zwei Setzungen sind Praeferenz und jetzt
als solche markiert: die Platzierung von #440 auf Platz 1 (folgt aus keinem der
Kriterien — es blockiert nichts und oeffnet nichts) und #430 vor #427.

Zwei echte Funde, beide behoben:

1. **`.github/PROJECT.md` §Reihenfolge trug noch die Erstfassungs-Sortierung**,
   waehrend die Datei anweist, ein fehlendes Queue-Issue „aus der Tabelle unten"
   neu zu bauen — ein Wiederaufbau haette die veraltete Reihenfolge
   zurueckgeholt. Tabelle steht jetzt in Queue-Reihenfolge.
2. **Zwei Tabellenzeilen waren sachlich falsch:** #430 und #427 als
   „Unabhaengig" bzw. „ohne Kopplung" beschrieben, obwohl beide eine
   Datei-Kollision haben (#430 nach #429 wegen `config.ts`/`LoginPage`, #427
   nach #436 wegen der OpenAPI-Artefakte). Gegen die Scope-Listen nachgeprueft.

Nebenbei korrigiert: #442 nannte PR #441 als „offen, Draft" — er ist seit
12:27 gemergt. Neuer Constraint in PROJECT.md: ein `size/M`-Issue wird nie
durch Nachtragen von Feldern startbar.


## Backlog-Reihenfolge verankert, Board bleibt Owner-Schritt (2026-09-05, 14. Lauf)

Anlass: die Frage, ob ein frisch gestarteter Agent bei „bearbeite ein Issue"
die richtige Reihenfolge kennt. Antwort war nein — sieben `agent-ready`-Issues,
alle `size/S`, kein Milestone (0 von 12), kein Board, keine Prioritaets-Achse,
und `.github/PROJECT.md` beschrieb noch das abgeschlossene v0.1.0-Vorhaben
(#338–#341). Die Reihenfolge stand nur als Prosa in einzelnen Issue-Bodies.

Owner-Wahl war Weg C (Projects-Board + `project.json`). **Die Board-Haelfte ist
mit dem Agenten-Toolset nicht baubar** (verifiziert): der GitHub-MCP-Server
dieser Session stellt keine Projects-Tools bereit (`projects_list`/`_get`/
`_write` fehlen, obwohl die Tool-Bindung sie nennt), `list_issue_fields`
liefert `[]` und es gibt kein Anlege-Tool dafuer, `gh` ist nicht verfuegbar.
Issue-*Types* existieren (Task/Bug/Feature), druecken aber Art aus, nicht
Reihenfolge.

Umgesetzt wurde deshalb die repo-seitige Haelfte, die auch ohne Board traegt:

- **`.github/PROJECT.md` neu geschrieben:** aktives Vorhaben „Cloud-Launch &
  Alltagstauglichkeit"; neuer Abschnitt **Reihenfolge** als erklaerte Quelle
  der Wahrheit (1 #440, 2 #429, 3 #434, 4 #430, 5 #436, 6 #427, 7 #438) mit den
  zwei harten Abhaengigkeiten (#429 blockiert #428 WP-4; #434 blockiert den
  Zuschnitt von #428 WP-2..5); Tracking-Issues, #435 und #338 ausserhalb der
  Nummerierung. Das alte v0.1.0-Vorhaben ist nach „Abgeschlossen" gewandert.
- **Regel gegen das Veralten:** ein neues `agent-ready`-Issue ohne Platz in der
  Liste gilt als unsichtbar; das steht als Acceptance-Kriterium in der Datei.
- **`.claude/project.example.json`** um `github_repo` und `project_number`
  ergaenzt, damit die spaetere (gitignorede) `project.json` das richtige Schema
  hat. Bisher trug die Vorlage nur Notion-Schluessel.

## Reihenfolge lebt im `backlog-queue`-Issue #442 (2026-09-05, Variante A)

Owner-Ziel: Agenten sollen die Reihenfolge **selbst** pflegen koennen. Das
Board taugt dafuer nicht — es ist fuer Agenten weder lesbar noch schreibbar.
Werkzeug-Inventar (gezaehlt, nicht geschaetzt): schreibbar sind Sub-Issue-
Reihenfolge (`reprioritize`), Labels, Body/Titel/Status, Issue-Type und die
Zuweisung bestehender Milestones; **nicht** schreibbar sind Projects-Board,
Issue-Fields (leer, nicht anlegbar) und Issue-Dependencies (`blocked_by`/
`blocking` sind im Payload sichtbar, es gibt kein Schreib-Tool).

Gewaehlt wurde Variante A: **ein Queue-Issue mit geordneter Task-Liste**
(#442, Label `backlog-queue`). Verworfen: Sub-Issues unter einem Queue-Parent
(ein Issue hat nur einen Parent — #434/#436/#438 haetten ihre Epic-Zuordnung
zu #428/#402/#431 verloren) und Queue-Labels (nur grobe Eimer, keine Sequenz,
keine Begruendung).

- **Stabiler Griff ist das Label, nicht die Nummer:**
  `list_issues(state=OPEN, labels=["backlog-queue"])` liefert genau eines.
  Fehlt es, baut der Agent es nach dem Muster in PROJECT.md §Reihenfolge neu.
- **Arbeitsteilung:** #442 traegt die Reihenfolge (umsortieren = ein
  `issue_write`, kein PR), PROJECT.md die Begruendung. Bei Widerspruch gilt
  fuer die Reihenfolge das Issue. PROJECT.md fuehrt deshalb keine
  Nummerierung mehr, sondern eine Tabelle „warum die Reihenfolge so aussieht".
- **Verifiziertes Risiko ausgeraeumt:** die Task-Listen-Referenzen in #442
  erzeugen KEINE Hierarchie — #434 haengt weiter unter #428, #438 unter #431,
  #442 hat keine Sub-Issues (per `get_parent`/`get_sub_issues` geprueft).
- Label `backlog-queue` entstand durch Zuweisung und hat wie die uebrigen
  Delegations-Labels keine Description (Owner-Klick).

Board inzwischen vom Owner angelegt: https://github.com/users/luetzey/projects/3
(`project_number: 3`), in PROJECT.md eingetragen. **Auch nach der Anlage bleibt
es fuer Agenten unsichtbar** — erneut geprueft, weder Projects-Tools noch
Issue-Fields; Pflege des Board-Status ist Handarbeit. Das Board ist laut Norm
eine Sicht auf die Liste, nicht ihre Quelle — PROJECT.md bleibt die Heimat, und
zwar zwingend, weil `project.json` gitignored ist und in einer Cloud-Session nie
existiert.

## Backlog-Refinement (2026-09-05, 13. Lauf — nur GitHub, kein Code)

Alle offenen Issues nach Playbook „Issue-Refinement" (Persona-Modus Refiner)
gegen die Norm „Agent-ready Arbeitspaket" (vier Pflichtfelder + Weichen) und
die Form-Norm „GitHub-Artefakt-Standards" geprüft; Owner-Entscheidungen F1–F8
im Gespräch eingeholt („Empfehlungen übernehmen").

- **agent-ready / size/S (startbar):** #427 (war es schon), #429 Coming-soon-
  Modus (Weg A entschieden — Runtime-Config-Muster; Compose kann keine Env
  ableiten → `GOTRUE_DISABLE_SIGNUP` bleibt explizit, `smoke.sh` prüft die
  Konsistenz), #430 auf WP-A „Angemeldet bleiben (12 h)" reduziert (Weg A
  `localStorage` + absolute Obergrenze, opt-in — Owner), #436 W0 Fehlercodes
  (Sub-Issue zu #402), #438 W0 Responsive-Fundament (Sub-Issue zu #431,
  Reihenfolge: nach Cloud-Launch-Block — Owner), #434 WP-1 Readiness-Inventar
  (aus dem Parallel-Lauf, s. 12. Lauf; mein #437 war ein Duplikat → geschlossen).
- **size/M (Tracking, braucht Zerlegung):** #428 (behält zusätzlich
  `needs-decision` aus dem 12. Lauf — meine Label-Zuweisung hatte es kurz
  überschrieben, wiederhergestellt), #431, #402 (Owner hat
  Option 1 „Fehler-Codes statt Prosa" entschieden; ADR-0051 folgt in #436),
  #435 Passkeys neu (aus #430 herausgelöst; GoTrue-WebAuthn braucht Image
  ≥ v2.163.0 — Repo pinnt v2.158.1; auth-js 2.112.3 kann es clientseitig).
- **human-only:** #338 (O2/O3 Owner-Klicks). **Geschlossen:** #341 (WP-10 lebt
  in #428 WP-4 weiter).
- Originalfassungen von #429/#430/#402 als Archiv-Kommentar gesichert, Bodies
  ersetzt (Konvention aus dem Playbook).

Befunde am Rande: der in #430 zitierte „Befund S1" existiert in
`docs/security-findings-phase-2.md` nicht (dort F-Phase2-01…03) — im Issue als
„zu verifizieren" markiert; `detail="`-Zählung ist 79, nicht 78 (#402);
CLAUDE.md nennt `npx tsc --noEmit`, CI fährt `npx tsc -b` (bekannt aus #427).

**Offene Owner-Klicks (kein Tool im GitHub-MCP):** Label-Descriptions für die
Delegations-Achse (`agent-ready`, `needs-decision`, `human-only`, `size/S`,
`size/M` — Vergabe-Regel laut Norm-Abschnitt Label-Semantik; `needs-decision`
und `human-only`/`size/M` wurden durch Zuweisung ohne Description erzeugt) und
zwei Milestones „Cloud-Launch" (#428, #429, #430, #434, #435) und „Mobile-fähige
UI" (#431, #438). `.claude/project.json` fehlt weiterhin (kein Board).

## Issue-Refinement #428 → `size/M` + `needs-decision`, WP-1 als #434 (2026-09-05, nur GitHub)

#428 ist ein Vorhaben (fünf WPs über API/Billing/Web/Deploy/Owner), kein
Arbeitspaket → Body um „Refinement-Stand" ergänzt (Original archiviert),
Labels `size/M` + `needs-decision`. Das erste startbare Paket WP-1 wurde nach
Playbook „GitHub-Artefakt anlegen & pflegen" als Sub-Issue **#434** angelegt
(`documentation`, `agent-ready`, `size/S`; Ausprägung A ohne Code: belegte
Checkliste in `.claude/plan/<ts>_cloud-launch-readiness-inventar.md`,
fortschreibend auf Juni-Plan + `docs/cloud-{local,prod}-smoke.md`).

Neuer Befund (belegt): die Pro-Feature-Codes `composite_playbooks`/`agents`/
`audit_export` werden nur ausgegeben (`routers/whoami.py:88`,
`routers/entitlement.py:72`, `BillingPanel`) und nirgends erzwungen; einzige
Durchsetzung ist `is_active()` in `services/mcp_limit_service.py:82`.
Offene Owner-Weichen als Kommentar auf #428: (1) Feature-Gates informativ
vs. hart (Empfehlung: hart, eigenes WP), (2) Cloud-Image-Deploy Registry-Pull
vs. Host-Build (Empfehlung: Registry-Pull). Label `needs-decision` ebenfalls
neu und ohne Description.

## Issue-Refinement #427 → `agent-ready` (2026-09-05, nur GitHub, kein Code)

Erster Lauf des Playbooks „Issue-Refinement" (Coder-Modus Refiner, Norm
„Agent-ready Arbeitspaket"). Body von #427 ersetzt (Original wörtlich als
Archiv-Kommentar), Titel in den Ergebnis-Modus, Labels `agent-ready` +
`size/S` (beide beim Setzen neu entstanden — grau, ohne Description; die
Vergabe-Regel aus der Norm steht noch nicht in der Label-Description).

Im Repo belegte Weichen (Auszug, vollständig im Issue): Datenmodell A
(`agent_favorite` pro User — die Owner-AC „pro User"/„Server-persistiert"
schließen B/C aus); **kein FK auf den User** (keine Tabelle referenziert
GoTrue-User, vgl. `0007`/`0049`) → User-Bereinigung über
`purge_account_data` statt CASCADE; RLS/Grants nach Muster 0066/0079;
`is_favorite` nur im List-Enrichment (`list_meta` + `AgentListMeta`);
PUT/DELETE `…/agents/{id}/favorite` → 204, human-only (403 für
agent-gebundene Tokens), kein `require_role`; Filter-Chip „Nur Favoriten"
raus (Review-Grenze). Befund am Rande: CLAUDE.md nennt `npx tsc --noEmit`,
CI fährt `npx tsc -b`.

Kein Milestone/Board (unverändert: `.claude/project.json` fehlt).

## Backlog-Issues aus dem Owner-Briefing (2026-09-05, nur GitHub, kein Code)

Fünf Issues nach Playbook „GitHub-Artefakt anlegen & pflegen" (Recherche
per Explore-Subagents, Fundstellen datei:zeile im Body, Duplikat-Suche
offen+geschlossen: 0 Treffer):

- **#427** Agents als Favoriten (Stern) — Design-Weiche A (per-User-Tabelle
  `agent_favorite`, Migration 0083) / B (`is_pinned` workspace-weit) /
  C (nur Client); Empfehlung A.
- **#428** Cloud-Edition launchen (Tracking, `epic`): Code ist fertig und
  ohne TODO, die Lücken sind operativ — Deploy-Job überspringt sich still
  (`deploy.yml:83`, `DEPLOY_HOST` fehlt), `smoke.sh` ohne Billing-Checks,
  Mollie-Keys leer. WP-1 Readiness-Inventar zuerst, WP-4 setzt #429 voraus.
- **#429** „Coming soon"-Modus per `WHO2BE_LAUNCH_MODE` — heute drei
  unabhängige Signup-Schalter (`GOTRUE_DISABLE_SIGNUP`,
  `WHO2BE_SIGNUP_DISABLED`, `VITE_WHO2BE_SIGNUP_DISABLED`) und stilles
  `Navigate` statt Hinweisseite (`SignupPage.tsx:73-75`).
- **#430** Login-Komfort: Ursache des 2FA-Prompts pro Tab ist die
  `sessionStorage`-Session (`lib/supabase.ts:5-39`, dokumentiert in
  `docs/mfa-admin.md:91-105`); WP-A „Browser merken" (opt-in, 12 h Max-Age,
  Security-Review Pflicht), WP-B Passkeys als GoTrue-WebAuthn-Zweitfaktor
  (Support in `gotrue:v2.158.1` zu verifizieren).
- **#431** Mobile-Tauglichkeit (Tracking, `epic`): 25/374 tsx-Dateien mit
  Breakpoints, kein Sheet/Drawer, Nav unter `sm` als Inline-Liste
  (`AppShell.tsx:63,90-105`), Playwright nur Desktop Chrome. Wellen W0–W4.

Verdrahtung: Labels aus dem Bestand (`enhancement`, `web`, `backend`,
`epic`); kein Milestone/Board gesetzt — `.claude/project.json` fehlt, kein
Projekt-Board bekannt (Owner-Entscheidung). Playbook-Feedback abgesetzt:
`fetch_resource(block_ids=[Heading])` liefert nur den Heading-Block, nicht
die Section — Schritt 3 des Playbooks ist so nicht ausführbar.


## Persona-Lookup per Name: serverseitiger Filter (2026-08-23, Issue #415)

Anlass: `get_persona("Builder")` brach im YouTube-Workspace mit einem
nichtssagenden Tool-Fehler ab, waehrend dieselbe Persona per UUID sauber lud.

- **Ursache:** Der Namens-Pfad (`client.py:295-302`) lud die GANZE Persona-Liste
  und verglich im Client. Da `PersonaRead` den vollen Body traegt, wanderte der
  ausgeschriebene Text jeder Persona ueber die Leitung, nur um einen String zu
  vergleichen — eine einzelne Persona rendert über 119.000 Zeichen, bei
  `_TIMEOUT = 10.0` und ohne Connection-Pooling ein Abbruch. Zusätzlich
  ignorierte der Scan die Pagination (`DEFAULT_LIMIT = 100`) und hätte ab der
  zweiten Seite „nicht gefunden" für eine existierende Persona gemeldet.
- **Fix:** `GET .../personas?name=` (exakt, kein `ILIKE` — der Pfad ist eine
  Auflösung, kein Suchfeld); der MCP-Client nutzt ihn, behält den
  `==`-Vergleich aber als Sicherheitsnetz gegen Versions-Versatz zur API.
- **Verifikation:** ruff/format/mypy grün, 1305 passed / 448 skipped.
  Coverage-Gate wie beim letzten Lauf lokal nicht prüfbar (kein Docker-Daemon)
  — CI bestätigt.
- **Offen:** Ob wirklich der Timeout zuschlug, klärt nur das Server-Log zu
  `request_id: req_011CeKm1LsS3nTPoKa4JjZvj`.
- **Nicht angefasst:** `_resolve_external_tool_by_alias` (`client.py:542`) hat
  dasselbe Scan-Muster, aber ohne grosse Bodies — eigener Befund, eigenes
  Ticket.

## MCP-Connector im Zweit-Workspace repariert (8. Lauf, 2026-08-23, Issue #413)

Anlass des Owners: ein zweiter Builder-Connector (Workspace „YouTube") schlug
bei **jedem** Tool mit `403 Token gehoert nicht zu diesem Workspace` fehl —
`whoami` eingeschlossen. Reproduziert gegen den laufenden Stack; der Connector
des Erst-Workspace lief im selben Moment sauber.

- **Ursache:** Der MCP-Server nahm den Workspace für seinen
  `/v1/workspaces/{id}`-Pfad aus `GET /v1/me` → `default_workspace_id`, also
  aus der *ersten Membership des Menschen* (nach Org-Alter sortiert) statt aus
  der Bindung des Tokens. Betraf deterministisch jeden User mit ≥ 2 Workspaces.
- **Fix (Stufe 1, PR zu #413):** `/v1/me` weist `token_workspace_id` aus, der
  MCP-Server bevorzugt es; eigener Taxonomie-Code `workspace_mismatch`
  (`actionable_by="human"`) statt des fehlgemappten `forbidden_transition`;
  `WHO2BE_WORKSPACE_ID` unter `transport=http` als Startup-Fehler abgelehnt
  (Multi-Tenant-Schutz).
- **Verifikation:** ruff/ruff-format/mypy grün, 1300 passed / 448 skipped.
  **Das 85-%-Coverage-Gate ist lokal nicht prüfbar** — die Sandbox hat keinen
  Docker-Daemon, alle DB-Integrationstests werden übersprungen (63,07 %). CI
  muss es bestätigen.
- **Nebenbefund:** `docs/reference/openapi.json` war stale (zog neben dem neuen
  Feld auch `OAuthConsentApprove.agent_id` aus #404 nach) — kein CI-Gate prüft
  die eingecheckte Spec gegen die App. Kandidat für WP-14.
- **Stufe 2 (ADR-0050, Entwurf — Entscheidung offen):** „MCP-Principal aus der
  Token-Introspektion". Vorschlag: read-only Introspektions-Endpunkt, Principal
  in den `AccessToken`-Claims, Wegfall von `_resolve_workspace_id`/`_WS_CACHE`,
  geteilter HTTP-Connection-Pool. Drei offene Owner-Fragen am Ende des ADR
  (Endpunkt-Name, Cache ja/nein, Zeitpunkt). Hintergrund:
  jeder MCP-Request introspectiert heute per `GET /v1/me` (schreibfähig, mit
  Lazy-Seed) und die Workspace-Auflösung ruft dasselbe `/v1/me` erneut; dazu
  prozess-lokaler Cache und kein HTTP-Connection-Pooling. Details in
  DECISIONS.md.

## Lokaler Ein-Befehl-Start (7. Lauf, 2026-08-23)

Ausgangsfrage des Owners: „Kann das jeder, der das Repo downloadet, ohne Frust
testen — auf localhost oder einer IP?" Plan:
`.claude/plan/2026-08-23-0811_local-one-command-start.md` (Scope A von A/B/C;
npm-CLI = Scope B bleibt offen).

- **Same-Origin statt fester Hosts.** Der nginx im web-Container proxied
  `/v1/` → `api:8000` und `/auth/v1/` → `auth-gateway:9999`. Der Browser spricht
  nur noch mit dem Origin, von dem er geladen wurde — `localhost`, LAN-IP oder
  Domain. CORS entfaellt fuer den lokalen Betrieb.
- **Runtime-Config statt Compile-Time.** `apps/web/src/config.ts` loest in der
  Reihenfolge `window.__WHO2BE_CONFIG__` (aus `/config.js`, vom nginx-Entrypoint
  aus Env geschrieben) → `VITE_*` → Same-Origin auf. Damit ist EIN Web-Image
  fuer Prod, localhost und LAN gueltig; der CI-Build backt keine URLs mehr ein,
  Hetzner setzt sie als Container-Env.
- **Kein `.env` mehr noetig.** Alle Compose-Werte haben Defaults;
  `WHO2BE_PUBLIC_URL` ist der eine Schalter fuer CORS, GoTrue-Allowlist und
  Invitation-Links.
- **MCP-Server im lokalen Stack.** Neuer Compose-Dienst `mcp` (HTTP-Transport,
  `:8765/mcp`) plus `^~ /mcp`- und PRM-Proxy im Web-nginx. Vorher war MCP lokal
  nur per `uv run python -m who2be_mcp.server` erreichbar — also ausgerechnet
  der Kern des Produkts nicht ohne Python-Toolchain testbar. Auth laeuft ueber
  einen normalen `w2b_`-Token (Bearer, verifiziert per `GET /v1/me`).
  Nebenbefund behoben: die Copy-Config der UI zeigte nach dem Same-Origin-Umbau
  auf `<origin>/mcp` und damit auf den SPA-Fallback (200 + HTML statt 401).
- **`docker-compose.images.yml`** zieht fertige GHCR-Images statt zu bauen.
  **Owner-Aktion offen:** die Packages `who2be-api|web|mcp` sind aktuell privat
  (anonymer Pull → 403) — public schalten, sonst bleibt der Build-Pfad Default.
- **Abnahme offen (Host):** Sandbox hat keinen Docker-Daemon. Zu pruefen sind
  `docker compose up -d --wait` ohne `.env`, Login/Bedienung ueber
  `http://localhost:5173` und ueber `http://<host-ip>:5173`, plus
  `bash scripts/smoke.sh`.

## i18n-Lücken geschlossen (2026-08-22, Issue #403 / PR #401)

Ausgangspunkt war „die Übersetzung auf dem Frontend funktioniert nicht".
Bestandsaufnahme: `.claude/plan/2026-08-22-0900_i18n-bestandsaufnahme.md`,
Umsetzungsplan `.claude/plan/2026-08-22-1000_i18n-luecken-schliessen.md`.

Der Unterbau war intakt (Probe-Render mit `changeLanguage` schaltet korrekt);
kaputt waren zwei Mechanik-Punkte und eine große untersetzte Fläche.

- **Sprach-Persistenz gehärtet.** `preferred_locale` ist jetzt ein Startwert;
  `markExplicitLocaleChoice()` / `shouldApplyStoredLocale()` in
  `src/i18n/index.ts` geben der Wahl im laufenden Tab Vorrang, ein User-Wechsel
  setzt zurück. Zwei Regressionstests in `useApplyStoredLocale.test.tsx`
  brechen gegen den alten Code.
- **Lazy statt eingefroren.** zod-Messages liefen über Modul-Level-`i18n.t()`
  und froren die Sprache auf den ersten Chunk-Load ein — jetzt Zod-4-Lazy-Form.
  Ein Test in `MembersPage.test.tsx` hatte den Bug als erwartetes Verhalten
  festgeschrieben (englische Meldung in deutscher Suite) und wurde korrigiert.
- **Abdeckung.** Harte deutsche Strings im Produktivcode: **117 → 11**
  (Rest bewusst: persistierte Pill-Labels, Entity-Namen-Defaults,
  `console.error`/Boot-Ausgaben). Neuer Namespace `editor` für den
  System-Prompt-Editor inkl. übersetzter Slash-Menu-Suchaliase.
  Locale-Keys: 1744 → **1902**, DE/EN weiterhin 0 Diff.

Offen: die 78 deutschen `detail`-Strings der API (Issue #402, braucht ADR).

**Test-Infrastruktur (2026-08-22):** In der Cloud-Session lässt sich PostgreSQL
16 + `pgvector` lokal starten; damit laufen die `@pytest.mark.integration`-Tests
wirklich statt sich zu überspringen — `1741 passed, 0 skipped`, Coverage
**91,21 %** (Gate 85 % erreicht). Ohne DB sind es `1293 passed, 446 skipped` bei
62 %, was das Gate reißen lässt und in mehreren PRs als „nur in CI belastbar"
ausgewiesen werden musste. Wer lokal verifiziert: DB hochziehen, sonst rutschen
genau die Tenancy-/RLS-Pfade durch, die am meisten wiegen.

**Nachtrag 2026-08-22 (Issue #408):** Der Umschalter war auf den öffentlichen
Seiten gar nicht erreichbar — er hing nur in `AppShell`, und alle Routen vor dem
Login liegen außerhalb von `AppLayout`. Die Bestandsaufnahme hatte auf
Key-Abdeckung gezählt und die Erreichbarkeit deshalb nicht gesehen; aufgefallen
ist es erst am realen OAuth-Consent. Jetzt bündelt `app/PublicLayout.tsx` diese
Routen und stellt die Sprach-Insel bereit (Login, Signup, Passwort-Reset,
Invitation-Onboarding, Consent, Legal). Dazu folgt `<html lang>` der aktiven
Sprache (`syncHtmlLang` in `src/i18n/index.ts`) — vorher statisch `de`, mit
Folgen für Screenreader und das Übersetzungsangebot des Browsers.
Plan: `.claude/plan/2026-08-22-1500_sprachumschalter-public-routes.md`.

## Standup-Folgearbeiten (2026-08-21)

Playbook „Projekt-Standup" gelaufen; Ergebnis war weniger offene Arbeit als
gedacht, dafür Drift in diesem Dokument.

- **Issue #388 (70 tote Branches löschen) war eine Karteileiche** und ist
  geschlossen: `list_branches` liefert für das Repo genau einen Eintrag,
  `main`. Die Löschung passierte am 2026-08-20 vor dem Flip, die im Issue
  empfohlene Ursachen-Behebung (Auto-delete head branches) ist aktiv.
- **Zwei Einträge dieses Dokuments widersprachen seinem eigenen Kopf:**
  §Bekannte Probleme führte „E2E-Gate bleibt Soft" und „CI seit 2026-08-19
  nicht gegeben", §Nächste Schritte forderte den `v0.1.0`-Tag — alles drei
  war am 2026-08-20 erledigt. Bereinigt; die Historie oben bleibt.
- **Neu gegengeprüft statt geglaubt:** `main` ist per API `protected:
  false` (Branch-Protection real offen), Repo hat weder Description noch
  Topics, Discussions sind an, 0 offene PRs, CI-Lauf `32483875971` grün.
- `CONTRIBUTING.md` §CLA stand noch auf „becomes active with the public
  switch" — auf den Ist-Zustand gezogen, Stelle für den CLA-Link markiert.
- Offen aus #341 bleibt allein **WP-10** (Deploy-Verifikation): der Job ist
  conditional auf `vars.DEPLOY_HOST` und überspringt sich still, solange
  die Variable fehlt. Nie rot, nie verifiziert — vor 1.0 Pflicht.

Plan: `.claude/plan/2026-08-21-1630_standup-followups.md`.

## Stale-Chunk-Recovery (2026-08-21, PR #399 / Issue #398)

User-Report „Unexpected error / Importing a module script failed" gefixt:
Nach einem Deploy liefen alte `React.lazy`-Chunk-Hashes ins 404, die
`RouteErrorBoundary` zeigte nur den Fehler. Jetzt: Stale-Chunk-Erkennung
(`apps/web/src/app/stale-chunk.ts`) + genau EIN Auto-Reload
(sessionStorage-Guard, 60 s-Fenster, Private-Mode-sicher) in Boundary und
`vite:preloadError`-Listener; `nginx.conf` liefert `index.html` mit
`Cache-Control: no-cache` (Assets bleiben `immutable`). DoD-Belege + Plan:
`.claude/plan/2026-08-21-1216_stale-chunk-auto-reload.md`.

## Public-Switch vollzogen + CI wiederbelebt (2026-08-20)

**Das Repo ist seit heute PUBLIC** (Owner-Flip ~13:00 UTC), PR #390 ist
gemergt (`e6ea003`), und die CI lief erstmals **komplett grün** inkl.
harter E2E-Spitze (Run `32377333096`: python 7:27 · web 6:15 · e2e 10/10
· compose-smoke · audit · 3× CodeQL).

- **Wurzelursache der CI-„Regression" seit 2026-08-19 ~16:37 gefunden:**
  KEIN Billing-Problem — die Actions-Policy „Require actions to be pinned
  to a full-length commit SHA" war aktiv geworden; jeder Lauf starb im
  „Set up job". Fix: alle 19 `uses:` in `ci.yml`/`deploy.yml` SHA-gepinnt
  (Tag als Kommentar für Dependabot). Die Policy bleibt bewusst an
  (Supply-Chain-Hardening).
- **E2E-Journeys erstmals real gelaufen und in 3 Runden repariert** (alle
  Fehler in der Spec, keine im Produkt): Promote-Validierung verlangt
  Body-Blocks schon bei draft→review; ResourcePicker zeigt Block-Optionen
  nur bei Heading-Blöcken; `@example.test` = Special-Use-TLD (pydantic
  lehnt ab, GoTrue nicht); `waitForURL` matchte `/playbooks/new` als ID;
  required Description ohne Testid blockte den Submit still; **Admin-MFA-
  Gate (aal2)**: der Helper macht jetzt echtes TOTP-Enroll gegen GoTrue
  (`/factors`→challenge→verify, RFC-6238 gegen Anhang-B-Vektor
  verifiziert) statt das Gate zu umgehen.
- **e2e ist hartes Gate** (#341 WP-9 komplett): `continue-on-error`
  entfernt nach grünem Beleg. **#338 O1 endgültig erledigt.**
- **Sicherheits-Setup nach dem Flip** (Owner): Dependency graph, Dependabot
  alerts/security updates, CodeQL (default) aktiv; Private vulnerability
  reporting, Secret/Push-Protection, Grouped updates, Malware alerts
  angestoßen.
- **Vor dem Flip bereinigt:** PR #314 geschlossen + Pitch-Dossier-Branch
  und `…-setup-4fk7ed` (Gateway-Reflexion) gelöscht (Inhalte dem Owner als
  Dateien gesichert); 72+2 tote Branches weg — Remote hat noch 5 Branches.
- **Release v0.1.0 IST LIVE** (2026-08-20 14:45 UTC,
  https://github.com/luetzey/who2be/releases/tag/v0.1.0): Tag auf `main`,
  Notes = CHANGELOG-0.1.0-Block. Weg dorthin: Git-Proxy darf keine Tags
  pushen und der Dispatch-API-Endpunkt war der Session verwehrt (403) —
  neuer Workflow `.github/workflows/release.yml` (workflow_dispatch:
  `gh release create --target` legt Tag + Release mit GITHUB_TOKEN an,
  Notes-Extraktion aus dem CHANGELOG, Idempotenz-Guard), einmalig über
  einen temporären Push-Trigger gefeuert und danach zurückgebaut. Künftige
  Releases: Actions → Release → „Run workflow" (Owner-Klick). **#341 WP-8
  damit erledigt; offen aus #341 nur noch WP-10 (Deploy-Verifikation, vor
  1.0).**

Ist-Zustands-Snapshot, kein Changelog. Die Umsetzungs-Historie (per-Run-Details,
Branch-Namen, DoD-Belege) lebt in `.claude/plan/*` (Status-Übersicht:
[`.claude/plan/README.md`](../plan/README.md)) und den gemergten PRs.

## Funktioniert (Ist-Zustand)

### Kern-App (Phase 1–3)

- Tenancy (`User → org_member → Organization → Workspace → Entity`), API hart
  auf `/v1/workspaces/{ws_id}/…`; Status-Workflow draft→review→active→inactive
  pro Version + Dashboard; RBAC `admin > editor > viewer` (ADR-0023) +
  Magic-Link-Invitations. Pläne:
  `.claude/plan/2026-05-27-1921_phase-2-vollwertige-app.md`,
  `.claude/plan/2026-05-29-1900_phase-3-ux-polish.md`.
- Resources + BlockNote-Insel (ADR-0022), Placeholder-Pills (ADR-0025),
  Composite-Playbooks/Persona-Modi/Resource-Tags (ADR-0024,
  `docs/agent-axes.md`), Content-i18n (ADR-0027), Einzel-Delete/-Export
  (ADR-0032), Account-Lifecycle + DSGVO-Purge/-Export.
- Listen-UX mit URL-Filtern (`useListFilters`/`ListFilterBar`: Status/Agent/
  Tag/Typ/Gruppierung), Playbooks- + Dashboard-Design-Refresh (Pläne
  2026-07-11/-12), MFA-Login-Step-up (`docs/mfa-admin.md`).
- Reload-sichere Deep-Links: `SessionProvider` exponiert `sessionLoaded`,
  `RequireAuth` wartet den Session-Bootstrap ab (Ladeanzeige statt sofortigem
  `/login`-Redirect) und gibt beim echten Logout die Ziel-URL als `?next=` an
  die LoginPage weiter — vorher warf jeder Reload den User aufs Dashboard.
- Dashboard-Aufmerksamkeits-Band zeigt neben offenen Entity-Reviews auch
  pending Memory-Vorschläge (ADR-0044, Link → Agents) und System-Prompt-
  Templates in Review (Link → `/system-prompts?status=review`); KPI-Felder
  `pending_memories`/`pending_system_prompts` (Plan
  `.claude/plan/2026-07-22-1650_dashboard-attention-memories-system-prompts.md`).
- Agenten-Übersicht zeigt pro Agent offene Gedächtnis-Vorschläge:
  List-Enrichment `pending_memory_count` (Batch-Aggregat, kein N+1) +
  klickbarer Aufmerksamkeits-Pill → Deep-Link `#memory` scrollt zur
  Gedächtnis-Sektion der Detail-Seite und hebt sie kurz hervor (Plan
  `.claude/plan/2026-07-24-1623_agents-pending-memory-badge.md`).
- **Sprache als durchgängiges Konzept (ADR-0045, ersetzt UI-Teil von
  ADR-0027; PR #357, Issues #348–#356):** ein Element = eine Sprache
  (`locale` auf der Identitäts-Zeile aller 5 Content-Typen, Migration 0069;
  System-Prompts erstmals mit Sprachwahl), Reads locale-agnostisch,
  `?locale=` als Listenfilter, `LocaleBadge` + Sprachfilter in der Web-UI,
  Workspace-`content_locale` bei Anlage (vorbelegt aus UI-Sprache,
  Personal-Workspace aus `preferred_locale`), automatische
  Output-Sprachanweisung im Agent-Renderer (`services/agent_language.py`),
  MCP-Tools mit locale-Metadatum + Builder-Sprach-Tagging, komplettes
  EN-Rollout-Paket (`repositories/builder_content.py` + `repositories/en/`,
  14 Sidecars) mit locale-bewusstem Seeding/Sync
  (`BUILDER_CONTENT_VERSION = 12`). Plan
  `.claude/plan/2026-07-24-1900_sprache-vertiefen-ein-element-eine-sprache.md`.

### MCP + OAuth

- MCP-HTTP-Transport (ADR-0034) + OAuth-2.1-Remote-Connector (ADR-0036,
  per-Agent-URL `.../mcp/a/<uuid>` — Agent im **Pfad**, seit 2026-08-22
  (#404, ADR-0036-Addendum); `?agent=<uuid>` bleibt rückwärtskompatibel,
  griff praktisch nie, weil Clients die Query aus der PRM-Resource
  verwerfen); Refresh-Reuse reject-only statt
  Ketten-Revocation (DECISIONS 2026-07-05); OAuth-Smoke beide Editionen grün.
- **Consent-Preview (2026-08-22, #405):** `POST /oauth/consent/preview` löst
  den gelockten Agenten über dieselbe Funktion auf, die später über
  Erfolg/403 entscheidet, und liefert Name + Workspace. Vorher zeigte der
  Consent eine rohe UUID, sobald der Agent nicht im Default-Workspace lag —
  und war bei leerem Default-Workspace gar nicht durchführbar. Kein
  Agent-ID-Parameter (IDOR), kein Existenz-Orakel. ADR-0036-Addendum 2.
- **Consent nur per Web-Session (2026-08-22, Security-Review zu #405):**
  `POST /oauth/consent` akzeptierte auch `w2b_`-Tokens und ignorierte deren
  Workspace-/Rollen-/Agent-Pins — ein herabgestufter PAT konnte sich darüber
  einen `admin`-Token prägen (`_issue` nimmt die aktuelle Membership-Rolle,
  nicht die gepinnte). `get_consent_principal` klemmt beide Consent-Endpunkte
  auf den JWT-Pfad. ADR-0036-Addendum 3. **Vorbestehend, nicht durch #405
  eingeführt** — gefunden, weil der neue Preview dieselbe Dependency erbte.
- **81 Tools** (58 + 23 aus WorkArea/KB/Tabellen, ADR-0047): Read + Write
  (ADR-0030), `search` + `search_content`
  (ADR-0037/0046), Versions-/
  Discovery-Tools, System-Prompt-Tools (ADR-0040), feinkörnige
  Agent-Schreibrechte inkl. Rate-Limit (ADR-0039). `tools/list` pro Agent
  policy-gefiltert (fail-open, SSoT `who2be_models.tool_requirements`,
  ADR-0042, PR #305) — neue Tools brauchen einen Mapping-Eintrag.

### Builder

- Managed Builder-Agent (Persona mit 3 Modi, 6 Playbooks, Konventions-
  Resource) + Managed-Lock, Deep-Copy-Duplizieren, Content-Start-Sync
  (`BUILDER_CONTENT_VERSION`, Stand 11 = `external_tool_write` +
  Playbook „External Tool anlegen & pflegen" + Konventions-Sektion;
  Stand 10 = Memory `suggest`/`recommended`). Befähigung + UI-Polish:
  PR #301/#302; Richtungsentscheidungen in DECISIONS 2026-07-09/-10/-11
  und 2026-07-21 (Memory-Triage/-Guard bewusst UI-only). Plan:
  `.claude/plan/2026-07-21-0810_builder-external-tool-write.md`.

### Feedback-Flywheel (ADR-0038)

- Append-only `usage_event` + `agent_feedback`, Triage
  (`feedback_resolution`), Posteingang inkl. System-Feedback
  (`report_problem`), Hard-Delete, Capability `feedback_resolve` +
  MCP-Tool `resolve_feedback`.

### Agent-Memory (ADR-0044)

- Kuratiertes Langzeitgedächtnis pro Agent: `memory_mode`
  off<read_only<suggest<auto + Freigabe-Schleuse pending→Triage→active;
  MCP `search_memory`/`list_memories`/`save_memory`, Laufzeit-Einbindung via
  `get_persona`, Placeholder-Kind `memory`; Injection-Wächter konfigurierbar
  (`memory_guard`, PR #327–#329). Pläne:
  `.claude/plan/2026-07-18-1500_agent-memory.md` + 2026-07-19-*.

### External Tools (ADR-0043)

- Versionierte Aggregate `external_tool` (instruktiv, Alias-Referenz),
  Placeholder `tool-ref` mit Fetch-Time-Expansion, 6 MCP-Tools + Web-Features
  (PR #316; Plan `.claude/plan/2026-07-18-1315_external-tools-tool-ref.md`).

### Editionen / Deploy

- Ein Codebase, zwei Build-Profile (ADR-0028/0029): `org_entitlement` als
  SSoT, On-Prem via `WHO2BE_LICENSE_KEY`, Billing build-isoliert
  (`packages/billing`, Web via `VITE_WHO2BE_EDITION`). Deploy
  `deploy/hetzner` (Caddy `api.`/`app.`/`mcp.`, `--profile mcp-http`).

### Standards / CI

- Standards-Schicht (`docs/standards/`, `AGENTS.md`, `.claude/context/`),
  FSL-1.1 + CONTRIBUTING/SECURITY (Public-Switch vorbereitet), OSS-Lizenz-
  Gates (ADR-0033), Test-Pyramide + Coverage-Ratchet (ADR-0041);
  Security-Findings Phase 1+2 alle Closed.
- Standards-Review 2026-07-08: WP-1–8 umgesetzt
  (`docs/standards-review-2026-07-08.md` §3); heutiger Lauf s. u.
- **CI-Gate: Regression seit 2026-08-19 ~16:37 UTC** — das alte
  Krankheitsbild ist zurück: jeder Lauf (main, Feature-Branches, Dependabot)
  bricht nach 2–8 s ab, `runner_id: 0`, keine Logs (Belege: Runs
  `32277214197` ff. bis `32359545985`; letzter echter grüner Lauf
  `32268362194`, 2026-08-19 15:09–15:21). Re-Run aus der Session nicht
  möglich (403). #338 O1 ist damit wieder offen — der Abschnitt darunter
  beschreibt den Stand 2026-08-16–19, als das Gate real lief:
- CI-Gate war 2026-08-16 bis 2026-08-19 aktiv (war zuvor seit 2026-07-19 durch
  Actions-Billing tot, GIT-2 im Standards-Review 2026-07-20). Alle fünf Jobs
  laufen: `python` · `web` · `e2e` · `compose-smoke` · `audit`. Beleg — das
  Krankheitsbild war Abbruch nach 2–6 s mit `runner_id: 0` und ohne Logs;
  jetzt echte Runner (`runner_id: 1000005113` ff.) und echte Laufzeiten
  (`python` 8 min inkl. Postgres-Service und voller pytest-Suite, `e2e`
  2:50 min mit Compose-Up + Playwright, `compose-smoke` baut zusätzlich das
  `runtime-cloud`-Image). Entscheidend: der erste Lauf (`31950241038`, PR
  #370) war **rot und zu Recht** — er fand zwei ESLint-Errors, die ein
  lokaler Lauf durchgelassen hatte. Ein Gate, das einen echten Defekt fängt,
  ist keins mehr auf dem Papier. Damit ist die lokale DoD-Ausführung wieder
  Vorstufe statt Ersatz.

### Release-Vorbereitung / Pre-Publish-Nachweis (2026-07-22)

- **Release-Audit** (Repo-Publish-Flow, Issues #338–#341): Ergebnis „noch
  nicht release-fertig" — Blocker waren npm-audit, fehlende NOTICES und der
  tote CI-Nachweis; Wellen 1–2 umgesetzt (dieser Run). Welle 3 (#341) wartete
  auf die CI-Reaktivierung — die ist seit 2026-08-16 da (s. §Standards / CI),
  der Block ist damit entsperrt.
- **Secrets-Gate bestanden:** kein Secret im Tree (nur Dev-/Test-Platzhalter
  und `${VAR}`-Injektionen); History sauber — nie `.env`/`.pem`/`.key`
  committet, gitleaks + 8 Pattern-Scans über alle Commits negativ
  (`.claude/plan/2026-05-27-2028_public-switch-github-repo.md`); **kein
  History-Rewrite nötig**.
- **npm-audit-Triage:** 3 CVEs (tar critical, undici + brace-expansion high)
  waren ausschließlich Dev-Tooling (eslint-Kette, jsdom, license-checker/
  node-gyp); `npm audit --omit=dev` war durchgehend clean → kein
  Runtime-Risiko. Per `npm audit fix` (nur Lockfile, 12 transitive Pakete)
  geschlossen; `npm audit` jetzt 0 Findings, Web-DoD danach grün
  (917 Tests, Coverage Statements 86,96 %/Branches 81,14 %).
- **Publish-Artefakte:** CODE_OF_CONDUCT.md (Contributor Covenant 2.1),
  ROADMAP.md, CHANGELOG.md, README-Ausbau, `LICENSE.md → LICENSE`,
  `THIRD-PARTY-LICENSES.md` + Generator
  (`scripts/gen_third_party_notices.sh`, OSS-1/ADR-0033).

## In Arbeit

- **Semantische Suche & Passage-Retrieval (ADR-0046)** — vollständig umgesetzt
  (Wellen 1–3).
  - *Welle 1:* `content_chunk` (Migration 0070, Schnitt an Heading-Blöcken,
    FTS-Config pro Sprache), Chunk-Aufbau im Transition-Pfad, `search_content`
    als REST + MCP-Tool (Passagen statt Aggregate), Backfill-CLI
    `who2be-retrieval-backfill`, plus zwei behobene Fehler der bestehenden Suche
    (Read-Scope hinter dem `LIMIT`; 403 auf Fremdtypen).
  - *Welle 2:* `content_vector` (Migration 0071, **fail-soft** ohne pgvector),
    asyncpg-Vektor-Codec mit dynamischer Schema-Auflösung, `EmbeddingPort` +
    lokaler fastembed-Adapter in der optionalen Dep-Gruppe `embeddings`,
    Hybrid-Ranking per RRF, `mode`-Parameter (`auto|text|semantic|hybrid`),
    Vektor-Backfill. Postgres-Images lokal/CI/Testcontainers auf
    `pgvector/pgvector:pg16`.
  - *Welle 3:* `content_vector` auf `agent_memory` (Migration 0072, fail-soft),
    `search_active` von der lexikografischen `ORDER BY`-Kaskade auf
    **RRF-Fusion über vier Zweige** umgebaut (FTS, ILIKE, Trigram, Vektor),
    semantischer Zweig im Dedup-Wächter, best-effort-Embedding im
    Laufzeit-Schreibpfad, Memory-Vektor-Backfill. Der MCP-Docstring, der seit
    ADR-0044 „semantisch" versprach, ist damit eingelöst.
  - Memory hat zwei komplementäre Testdateien: die Baseline hält fest, was der
    lexikalische Pfad kann und wo seine Grenzen liegen; `test_memory_semantic`
    belegt, dass der Vektor-Zweig genau diese Grenzen löst — ohne die
    lexikalischen Fähigkeiten zu verdrängen.
  - *Nachzug (2026-07-26, Content-Stand 14):* Der Builder weiß jetzt, was das
    Feature von ihm verlangt — neuer Abschnitt „Auffindbarkeit & Retrieval" in
    den Agent-Bau-Konventionen (Überschriften sind Chunk-Grenzen, nur aktive
    Versionen sind auffindbar, Passage vor Volltext, `mode`, Sprachgrenze) +
    semantisches Gedächtnis in der Memory-Sektion; `search_content` in Persona
    und Playbooks (DE + EN). Dazu die dabei gefundene Lücke geschlossen: Seed
    und Start-Sync schreiben aktive Versionen an `_transition` vorbei, ein
    frischer Workspace hatte deshalb **null** Passagen — beide Pfade stoßen den
    Chunk-Lauf jetzt selbst an (Seed gescopet, Start-Sync nur nach
    Content-Bump).
  - **DoD:** Python 1256 pytest / Coverage ~90 %; ruff + format-check + mypy
    grün; Web unberührt (keine Änderung unter `apps/web/`).
  - **Offen:** Kalibrierung der drei Schwellen (`_MIN_VECTOR_SIMILARITY` je
    Korpus, `_DEDUP_VECTOR_SIMILARITY`) gegen das reale Modell — der
    Modell-Download ist in der Entwicklungsumgebung per Netz-Policy gesperrt.
    Die Retrieval-Mechanik ist gegen deterministische Test-Vektoren mit
    bekannter Geometrie belegt, die Modell-Qualität nicht.
- **Standards-Review 2026-07-20** (`docs/standards-review-2026-07-20.md`,
  PR #331): Phase A mit 12 Prüf-Agenten; Phase B Wellen 1–3 umgesetzt
  (SEC-1/2/3, LIC-1, DEP-1/2/6, LIC-4, OSS-2, FE-1/10/11, Kosmetik-Sweep,
  GIT-8, Memory-Pflege). **DoD:** Python 1155 pytest / Coverage 89,74 %;
  Web 912 Vitest / Branches 81,07 %; alle Gates lokal grün.
- OAuth-Connector: E2E mit echtem Claude/ChatGPT-Client offen; TTL-Cleanup
  der OAuth-Tabellen, optionale Audience-Trennung, aal2-Consent (Phase 2).

### Agent WorkArea + Knowledge Base (ADR-0047/0048/0049) — WP1–WP20 umgesetzt

Zweite Achse neben der kuratierten Resource-Achse: **unversionierter
Arbeitsbereich** für Agenten plus **belegpflichtige Knowledge Base**. Plan
`.claude/plan/2026-08-13-1200_agent-workarea-knowledge-base.md` (20 WPs in
7 Wellen), PR #367.

- **WorkArea:** `work_area` (private je Agent, auto-angelegt; shared per
  Grant — Grant-Vergabe ist Menschen-Sache), `wa_artifact` (doc/table/blob,
  `occurred_at` als Pflicht-Input ohne `now()`-Fallback, optimistische
  Nebenläufigkeit über `rev`), `wa_chunk` als **eigener** Suchindex
  (`content_chunk` bleibt unangetastet — kuratierte und arbeitende Achse
  trennen auch im Retrieval).
- **Ingest (Pipeline B):** Datei-/URL-Ingest mit 20-MB-Limit, SSRF-Schutz,
  content-addressed Blob-PUT (`blobs/{ws}/{sha256}`) vor **einer** Postgres-
  Transaktion; Doppel-Ingest dedupliziert ohne zweites Objekt.
- **BlobStore (ADR-0048):** Port + MinIO-/In-Memory-Adapter; ohne
  `WHO2BE_BLOBSTORE_*` liefern nur Ingest/Blob-Reads 503, alles andere läuft
  unverändert (gültiger Betriebsmodus).
- **Tabellen-Store (ADR-0049):** SQLite je Area, Datei = Isolationsgrenze;
  read-only als Engine-Garantie (`mode=ro` + `query_only` + Authorizer mit
  Opcode- **und** Funktions-Allowlist + Zeit-/Zell-/Result-Budgets).
  Deterministische Kategorisierung + Quellen-Konventionen; Timeline-Merge.
- **Knowledge Base:** Belegpflicht je Aussage (`source_ref`), Tier-Regeln
  (`verified`/`derived`/`hypothesis`), Kanten inkl. Korrelations-Disziplin
  (`co_occurs_with` nur mit n ≥ 20 + Zeitfenster), Konflikt-Erfassung.
- **Compliance:** `agent_access_log` (Auto-Protokoll, Modell-/Sensitivitäts-
  **Snapshot** zum Zugriffszeitpunkt, FK `NO ACTION`), Betreiber-Query in
  `docs/compliance/agent-access-log.md`; VVT V18–V20.
- **Retention (WP20):** `who2be-purge` deckt jetzt drei Speicher ab —
  `cleanup_expired_artifacts` (Area-Frist `retention_days`, Default `NULL` =
  unbegrenzt, auch privat), `cleanup_orphan_blobs` (Katalog-Zeile ohne
  Artifact **und** Objekt ohne Zeile, je > 24 h; Objekt-Sweep nur mit
  Storage-Zeitstempel) und `cleanup_deleted_area_stores` (SQLite-Dateien
  gelöschter Areas). GDPR-Export trägt Areas/Artifacts/Blob-Metadaten/
  Tabellen-Zeilen (Cap 10 000 + `truncated`)/KB/Zugriffslog.
- **MCP:** 58 → **81 Tools** (`tools/workarea.py`, `tools/tables.py`,
  `tools/kb.py`), policy-gefiltert, Payload-Budget grün.
- **Security-Reviews:** nach Welle 2 und Welle 5 je ein Durchlauf; Phase 2
  siehe eigener Abschnitt unten.
- **DoD (2026-08-16):** `ruff check` + `ruff format --check` (439 Dateien) +
  `mypy .` (439 Quellen, strict) grün; **1632 pytest gesamt, Coverage 90,98 %**
  (Gate 85 %); `apps/api/tests` allein 1152 grün.
- **Bewusst offen:**
  - *P1-Backlog:* KB-TTL-Verfall (`ttl_expires_at` wird gesetzt, aber nicht
    automatisch ausgewertet), Challenger-/Gegenbeleg-Mechanik,
    Drift-Erkennung auf Aussagen.
  - *P2-Backlog:* Graph-Visualisierung der Kanten, semantische Suche auf
    `wa_chunk` (Vektor-Zweig wie ADR-0046 auf der Resource-Achse) — die
    Tabellen-UI ist seit 2026-08-19 umgesetzt (s. u.), KB bleibt API-/MCP-only.
  - *Manuelle Compose-Verifikation steht aus* (WP3-Punkt): `docker compose up`
    → minio healthy → Bootstrap legt Bucket an und terminiert → ohne
    Blobstore-Env Ingest = 503 → mit Env PDF-Ingest-Smoke, Objekt unter
    `blobs/{ws}/{sha}`, Doppel-Ingest ohne zweites Objekt. Braucht eine
    Umgebung mit Docker; in der Entwicklungsumgebung nicht ausführbar.
  - *Tabellen-Import kappt Zell-Breiten nicht* — s. §Bekannte Probleme.

### Security-Härtung Agent-WorkArea (2026-08-16, Phase-2-Review)

Zweiter Review-Durchlauf über Tabellen-Store, Zugriffslog und Promote
(Commits `73fe887..6a8638e`); alle Findings umgesetzt, Regressionstests in
`apps/api/tests/test_security_fixes_phase2.py`, Begründungen im
ADR-0047-Nachtrag 2026-08-16 und in DECISIONS.

- Freies Agenten-SQL hat jetzt Ressourcen-Grenzen: Zeitbudget je Query/
  describe (408), Zell-Cap 1 MB und Result-Budget 2 MB (413). Der Authorizer
  prüft SQL-Funktionen namentlich (`fts3_tokenizer` & Co. verweigert).
- Zugriffslog ist fälschungsfest: Modell-Config wird zum Zugriffszeitpunkt
  gesnapshottet (Migration 0080), agent-gebundene Tokens dürfen sie nicht
  setzen, und der FK hält gegen Cascade-Löschung (Agent-Delete mit
  Protokollzeilen → 409, Purge bleibt der Löschpfad).
- Kleineres: Rate-Limit vor der Query (`peek_write_rate`), Markdown-/
  CSV-Injektion im server-gerenderten Export, Timeline-Existenz-Orakel und
  -Quellen-Deckel, Promote-Aktor + Längen-Schnitte.

### Arbeitsbereich in der Web-UI + Builder-Rechte (2026-08-16)

Das WorkArea/KB-Feature war nach PR #367/#369 **nur über MCP erreichbar** —
die drei Betreiber-Stellschrauben lagen in der Web-UI brach. Nachgezogen:

- **Agenten-Editor:** `workarea_write`/`kb_write`/`kb_edge_write` sind
  Checkboxen im Policy-Editor; ohne sie konnte ein Betreiber einem
  Fach-Agenten den Arbeitsbereich gar nicht freischalten. Dazu eine Sektion
  „Modell-Konfiguration" (`model_provider`/`model_name`) — das Feld ist
  Menschen vorbehalten und war damit ohne UI **tot**, obwohl die
  Compliance-Auskunft des Zugriffslogs daran hängt.
- **Modell-Config ist wieder leerbar:** `AgentUpdate` hatte `min_length=1` +
  COALESCE, ein gesetzter Wert war nicht mehr zu entfernen (der Code nannte
  das selbst einen offenen Punkt). Neuer Vertrag: `''` = explizit auf NULL,
  weggelassen = unverändert; Drei-Wege-`CASE` im Repository, Audit greift.
- **Neuer Endpunkt `GET /work-areas/{area_id}/grants`** (Menschen-only,
  Viewer dürfen lesen) — der Grant-Editor braucht den Ist-Stand, es gab nur
  `PUT`/`DELETE`.
- **Lese-Ansicht `features/workarea`:** Bereiche (+ Anlage geteilter
  Bereiche), Bereichs-Detail mit Inhalten und Freigaben, Artifact-Ansicht mit
  Block-Ankern, WorkArea-Suche und Knowledge-Base-Suche/-Detail inkl.
  Beleg-Rückverweis und Fallzahl bei `co_occurs_with`.
- **Builder darf die Tools nutzen** (`BUILDER_CONTENT_VERSION` 14 → 15): rein
  policy-seitig, der Start-Sync verteilt es an Bestands-Builder. Ohne die
  Flags könnte der Builder sie wegen `is_within` auch keinem Fach-Agenten
  vergeben — das ist der eigentliche Zweck.

Zwei bewusste Entscheidungen der Lese-Ansicht: Artifact-Inhalte werden als
**Rohtext mit Ankern** gerendert (kein Markdown→HTML — der Inhalt stammt von
Agenten und aus Ingest-Fremdquellen), und `url:`-Belege der KB bleiben
**unverlinkter Text** aus demselben Grund. Einziger Inhalts-Write der UI ist
das Löschen eines Artifacts (editor+).

**DoD:** Python 1639 pytest / Coverage 90,98 %; Web 970 Vitest (Statements
86,2 %, Branches 80,43 %); ruff/mypy/tsc/lint/build lokal grün.

### Tabellen-Store war im Deployment unbenutzbar (2026-08-16, behoben)

Beim Live-Test der Tabellen-Achse antwortete `create_table` mit **500**.
Ursache war eine Folge meines eigenen Fixes aus PR #369: das dort ergaenzte
Named Volume auf `/data/tablestore` legt Docker als `root:root` an, weil das
Image das Verzeichnis nicht mitbringt — der API-Container laeuft aber als
`USER who2be` (uid 1000). Damit scheiterte schon das `mkdir` in
`tablestore/engine.py::_connect_rw` mit `PermissionError`.

Der Volume-Fix hat also den stillen Datenverlust beseitigt und dabei das
Schreiben ganz verhindert. Verifiziert war damals nur `docker compose
config`, nie ein echter Schreibvorgang — die Luecke lag zwischen
„Konfiguration korrekt" und „funktioniert".

Zwei Teile behoben (PR #372):

- `apps/api/Dockerfile` legt `/data/tablestore` im Image an und uebergibt es
  dem Service-Nutzer; Docker uebernimmt Eigentuemer und Rechte beim ersten
  Mount eines leeren Named Volume.
- Neuer Reason `tablestore_unavailable` (503): Datei-/Rechte-Fehler des
  Stores werden zentral uebersetzt (`services/wa_tables._store_failures`)
  statt als nacktes 500 durchzulaufen. Der Detail-Text nennt die
  Stellschraube, nicht Pfad oder OS-Fehler; die Ursache steht im Log.

### `describe_table` antwortete mit 500 (2026-08-16, behoben)

Der Live-Test nach dem Redeploy zeigte: der Tabellen-Store hat überlebt (7
Zeilen, `query_table`/`timeline`/`list_category_rules` alle 200) — nur
`describe_table` lief in ein **500**. Die Volume-Hypothese war damit
widerlegt; der Fehler steckte in Postgres, nicht in SQLite.

Ursache war eine Kette aus drei für sich harmlosen Teilen:

1. `upsert_convention` band `json.dumps(convention)` an `$4::jsonb`. Der Cast
   aktiviert den jsonb-Codec des App-Pools (`core/db.init_connection`,
   `encoder=json.dumps`) — der String wurde ein **zweites** Mal verpackt, in
   `wa_source_convention.convention` stand ein JSON-*String*.
2. Für dieselbe Zeile gab es **zwei** Mapper. Der tolerante
   (`wa_rule_repository`) trug alles, was über die Regel-/Konventions-Routen
   lief; der strenge (`wa_table_repository`) hing an genau einem Aufrufer —
   dem describe-Pfad — und starb an der Zeilenform.
3. Kein Test deckte die Kombination: der einzige describe-Test prüfte
   `conventions == []`.

Folge im Betrieb: sobald eine Area der dokumentierten Reihenfolge folgte
(Konvention setzen → importieren), war `describe_table` für diese Area tot —
ausgerechnet das Tool, das Agenten als „DER Einstieg vor jeder Query"
angeboten wird. Die Web-UI war nicht betroffen (sie ruft describe nicht auf).

Behoben (PR folgt in diesem Branch):

- **Write:** `upsert_convention` bindet das dict; `memory_guard` ebenso.
  `audit_log.detail` nutzt `$6::text::jsonb` — diese Form ist auf beiden
  Connection-Arten korrekt, weil der Executor dort offen ist.
- **Ein Mapper:** die Kopie in `wa_table_repository` ist entfallen, der
  Service liest Konventionen über `wa_rule_repository`.
- **Bestandsdaten:** Migration `0081` packt doppelt encodierte Werte aus
  (`wa_source_convention`, `workspace.memory_guard`); `audit_log` bewusst
  nicht — ein Audit-Trail wird nicht rückwirkend umgeschrieben.
- **Regressionsschutz:** ein Roundtrip-Test hätte nichts gefunden (der
  tolerante Leser hält ihn grade), deshalb prüfen die Tests den
  **gespeicherten Zustand** (`jsonb_typeof = 'object'`), dazu describe mit
  gesetzter Konvention, ein Migrationstest gegen nachgestellten Altbestand
  und ein Drift-Guard über alle Repositories.

### Suchtreffer-Anker lieferte nur die Überschrift (2026-08-16, behoben)

Befund A aus dem Builder-Test. Der dokumentierte Weg lautet
`search_workarea` → `read_artifact(anchor)`. Der Treffer-Anker ist per
Konstruktion die `block_id` des **Heading-Blocks** der Passage
(`wa_chunks.build_chunks`) — der Lesepfad gab darauf aber genau diesen einen
Block zurück. Der Agent bekam also `## Fehlercodes` ohne eine Zeile Inhalt
und musste doch das ganze Dokument laden, also genau das, was die Suche
vermeiden soll.

Warum es kein Test fand: der bestehende End-to-End-Test benutzt ein Dokument
aus EINEM Absatz ohne Überschrift. Dort sind „ein Block" und „die Passage"
dasselbe — die einzige Dokumentform, in der beide Verhalten
ununterscheidbar sind.

Behoben: `wa_chunks.split_sections` ist jetzt die gemeinsame Quelle der
Passagen-Grenzen für Index UND Lesepfad; `passage_for_anchor` löst einen
Anker auf. Ein Anker, der eine Passage eröffnet, liefert die ganze Passage
(bis zur nächsten Überschrift); jeder andere Anker weiterhin genau seinen
Block — das ist der Blick vor einem `patch_artifact`. Die Tool-Beschreibungen
in `apps/mcp` sagen beide Fälle jetzt an. Gegenprobe gefahren: ohne den Fix
liefert der Read `'## Fehlercodes [#…]'`, der neue Test wird rot.

### KB-Suche fand keine deutschen Wortformen (2026-08-17, behoben)

Befund B aus dem Builder-Test. `kb_node.search` indizierte mit
`to_tsvector('simple', content)` (0077) und die Abfrage nutzte konsistent
`plainto_tsquery('simple', …)` — kein Mismatch, aber **kein Stemming**. Eine
Aussage über den „Fehlercode" war damit für eine Suche nach „Fehlercodes"
unsichtbar, während `search_workarea` denselben Text fand (`wa_chunk` bildet
über `locale` auf `german`/`english` ab). Für einen Agenten ist der
Unterschied nicht lesbar: kein Treffer sieht aus wie kein Wissen.

Die Begründung in 0077 („Aussagen sind kurz und ggf. gemischtsprachig")
bleibt dort stehen; 0082 revidiert die Entscheidung, weil ihr Preis im
Betrieb sichtbar wurde. `workspace.content_locale` (0069) sagt längst, in
welcher Sprache ein Workspace schreibt.

Behoben: Migration `0082` gibt `kb_node` eine `locale`-Spalte (Backfill aus
dem Workspace) und ersetzt die generierte `search`-Spalte durch die
locale-abhängige Config — der Neuaufbau der Spalte **ist** der Reindex.
`services/kb.create_node` leitet die Sprache serverseitig über den
bestehenden `resolve_content_locale` ab; `KbNodeCreate` bekommt bewusst
**kein** `locale`-Feld.

Dazu: die Abbildung Sprache → Textsuch-Config lag zweimal wörtlich identisch
im Code (`content_chunk_repository`, `wa_search_repository`). Statt einer
dritten Kopie gibt es jetzt `repositories/fts_config.fts_config_expr`, das
alle drei Suchpfade nutzen. Gegenprobe: alle drei neuen Tests waren vor dem
Fix rot (`Fehlercodes` → `[]`, fehlende Spalte, fehlender Backfill).

### MCP verschluckte die Reason-Codes (2026-08-17, behoben)

Befund C aus dem Builder-Test. Die API antwortet an ihren Gates mit
`application/problem+json` und trägt dort `reason` — ein geschlossenes
Vokabular, ausdrücklich gebaut, damit „ein Agent darauf deterministisch
verzweigen kann, ohne den `detail`-Freitext zu parsen" (`models/errors.py`).
Der MCP-Client hat genau dieses Feld verworfen: bei 403/409/422 reichte er
nur `detail` durch, bei allen übrigen Statuses (400/408/413/429/503) nicht
einmal das — der Agent sah `Who2Be-API-Fehler (503).` und konnte weder
erkennen, dass ein Retry sinnlos ist, noch warum.

Behoben: eine Stelle (`client.problem_message`) statt zwei, angewandt auf
**alle** Fehler-Statuses. Die Meldung führt weiter mit der Prosa und hängt
`(reason=…, actionable_by=…)` an — greppbar, ohne den Lesefluss zu stören.
Antworten ohne Taxonomie (FastAPI-`HTTPException`, Validierungsfehler)
bleiben unverändert; es wird nichts erfunden. Gegenprobe: die neuen Tests
sind ohne den Fix rot, u. a. mit `Who2Be-API-Fehler (503).` statt der
Begründung.
### Tabellen waren für Agenten unauffindbar und unlöschbar (2026-08-17, behoben)

Aus dem Agentenbetrieb gemeldet, alle Teilbehauptungen geprüft: es gab kein
`list_tables` über MCP (wohl aber `list_category_rules` — man konnte die
*Regeln* auflisten, nicht die Tabellen); der 409 bei Namenskollision verwies
auf `GET /work-areas/{area_id}/tables`, also auf einen REST-Pfad ohne Tool;
`search_workarea` indiziert Artifact-Passagen und `timeline` verlangt die ID
bereits. Ein Agent konnte eine Tabelle anlegen und sie im nächsten Lauf
strukturell nicht wiederfinden. Löschen ging gar nicht — jeder Ausweichname
hinterließ eine Leiche.

Die API konnte das Listing die ganze Zeit; es fehlte nur die letzte Meile zum
Agenten — dieselbe Klasse wie Befund C (Reason-Codes).

Behoben: MCP-Tools `list_tables` (mit `area_id=None` = private Area) und
`delete_table`; der 409 nennt jetzt die **ID der bestehenden Tabelle**, womit
sich auch ein Agent ohne Listing selbst heilt; neu `DELETE /wa-tables/{id}`
plus `TableStore.drop_table` — Katalog-Delete und `DROP TABLE` atomar wie beim
Anlegen, damit nie „Katalog leer, SQLite-Tabelle liegt noch da" entsteht (das
würde den Namen dauerhaft verbrennen). Die Auflösung von `area_id=None` liegt
jetzt einmal in `tools/area_ref.py` statt je Tool-Familie.

Bewusst nicht mitgelöscht: eingefrorene `save_query_result`-Artifacts (sie
sind eigenständige Belege für bereits zitierte Zahlen) sowie Regeln und
Konventionen, die an der Area hängen.

### Aufräumen nach der WorkArea-/KB-Session (2026-08-19)

Gezielt gegen die Fehlerklasse, die an diesem Wochenende dreimal zugeschlagen
hat — *eine Sache, zwei Definitionen* (#375 doppelter Konventions-Mapper →
500; #376 zwei Passagen-Grenzen → Treffer ohne Inhalt; #377 fast eine dritte
FTS-Config).

- **`_snippet`** lag zweimal byte-identisch vor (`kb_repository`,
  `wa_search_repository`) → `repositories/snippet.py`. Beide Suchpfade
  liefern „Anker + Kostprobe"; wäre die Grenze verschieden, hinge die
  Snippet-Länge davon ab, welcher Index zufällig getroffen hat.
- **Test-Helfer** lagen bis zu 15-fach vor — `_agent_token` in **fünf
  verschiedenen Fassungen** (mit/ohne `role`, `prefix` vs. `base_prefix`, zwei
  gaben nur die Header statt `(agent_id, headers)`). Jetzt einmal in
  `who2be_api.testing.api_helpers` (neben `workspace_setup`, dem etablierten
  Ort): `agent_token`, `shared_area`, `grant`, `db_fetchval`, `db_execute`.
  Damit ist die `conftest.py`-Regel aus dem TST-10-Audit eingelöst („der
  Bestand wird inkrementell abgebaut, nicht vermehrt").

Diff: 221 Zeilen dazu, 691 weg. Beleg für „verhaltensneutral": **1679 Tests
vorher wie nachher**, Coverage 91,11 %, und keine inhaltliche Assertion im
Diff — die 46 entfernten `assert`-Zeilen sind ausschließlich die
Setup-Prüfungen der Helfer selbst, die jetzt einmal statt fünfzehnmal stehen.

Offen aus dem Aufräum-Plan: Rendering/Entschärfung aus
`services/wa_tables.py` und SQL-Bau aus `services/wa_rules.py` (Stufe 3).

### Aufräumen Stufe 3 (2026-08-19) — abgeschlossen

Letzter offener Punkt aus dem Aufräum-Plan, verhaltensneutrale Extraktion,
keine neue Logik. Plan: `.claude/plan/2026-08-19-1500_stufe3-wa-render-tablestore.md`.

- **Render-/Entschärfungs-Helfer** aus `services/wa_tables.py` (880 → 755 Z.)
  nach `services/wa_render.py` (neu, 168 Z., reine Funktionen — kein I/O, kein
  `ApiGateError`). Umbenannt: `_render_markdown` → `render_table_markdown`,
  `_render_csv` → `render_table_csv`, `_compose_result_doc` →
  `compose_result_doc`, `_csv_cell` → `csv_cell`, `_CSV_FORMULA_PREFIXES` →
  `CSV_FORMULA_PREFIXES`. Sprechende Namen statt einer dritten
  `_render_markdown`-Definition — `entity_export_service._render_markdown`
  und `wa_blocks.render_markdown` existieren bereits, alle drei tun etwas
  anderes. Einzige Teständerung: der Import in `test_security_fixes_phase2.py`.
- **SQL-Bau** aus `services/wa_rules.py::_reapply_sql` (+ `_like_parameter`) in
  `TableStore.reapply_category(...)` (`tablestore/engine.py`) gezogen
  (`wa_rules.py` 360 → 332 Z.). `wa_rules.py` kennt jetzt kein SQL mehr — die
  ARC-3-Leitplanke (kein SQL in `apps/api/**/services/`) ist für die
  WorkArea-Services damit buchstäblich erfüllt. Die redundante
  Doppel-Validierung `quote_identifier(validate_identifier(...))` entfiel
  (`quote_identifier` validiert intern).

Neutralitätsbeweis: volle Suite vorher wie nachher **1681 passed**, keine
inhaltliche Assertion im Diff.

### Aufräumen Stufe 2 (2026-08-19) — zwei echte Defekte statt Kosmetik

Beide Punkte, die als „Aufräumen" auf der Liste standen, waren bei näherem
Hinsehen Fehler mit Wirkung. Beide zuerst als reproduzierender, failing Test.

**1. Zell-Cap fehlte im Schreibpfad — die Tabelle wurde unlesbar.**
`_connect_ro` setzt `SQLITE_LIMIT_LENGTH = MAX_CELL_BYTES` (1 MB), `_connect_rw`
nicht; `_validate_rows` prüfte Spalten, Skalare, NOT-NULL und `occurred_at` —
Größe nicht. Gemessen: eine 2-MB-Zelle wird geschrieben, danach endet **jedes**
`SELECT` auf die Spalte in `SQLITE_TOOBIG` (nur `count(*)` läuft noch). Ein
Agent konnte sich sein eigenes Material vergiften, ohne dass der Import etwas
meldete. Jetzt 422 vor dem Write, gegen dieselbe Konstante aus dem Store —
keine zweite Zahl im Service. ADR-0047-Nachtrag.

**2. Der System-Prompt versprach Tools, die `tools/list` herausfiltert.**
`_ToolDoc.is_visible` ist ein Gruppen-Oder, gedruckt wird aber die ganze
Signatur samt Beschreibung. Die gemischten Gruppen (WorkArea, KB, Tabellen)
nannten einem Agenten mit Default-Policy **13 Schreib-Tools**, die die
`PolicyFilterMiddleware` gleichzeitig entfernt — der Agent probiert etwas, das
er nicht hat. Damit war die ADR-0042-Zusage „Prompt-Text und echte Tool-Liste
können nicht mehr widersprechen" für diese Gruppen falsch; die SSoT war nicht
das Problem, die Granularität der Gruppierung schon. Jetzt umfasst eine Gruppe
nur Tools mit **derselben** Sichtbarkeitsbedingung (`promote_artifact` und
`create_edge` stehen allein — andere Capability als ihre Nachbarn), und die
Beschreibungen nennen nichts Unsichtbares mehr. ADR-0042-Nachtrag.

Nebenbefund: `test_full_policy_shows_all_curated_groups` war nie voll —
`workarea_write`/`kb_write`/`kb_edge_write` fehlten in seiner Policy, was das
Gruppen-Oder verdeckte. Der Test gleicht seine Policy jetzt gegen
`AgentToolPolicy.model_fields` ab, damit eine neue Capability ihn rot macht.

Absicherung gegen Rückfall: `test_prompt_nennt_kein_tool_das_die_policy_
herausfiltert` prüft über die SSoT statt über eine Namensliste. 1681 Tests
grün, Coverage 91,09 %.

### Tabellen-UI + WorkArea-Exporte (2026-08-19)

Schließt die in §Bekannte Probleme dokumentierte Asymmetrie „Artifacts sind
sichtbar, Tabellen nicht" (gefunden 2026-08-17) UND liefert Datei-Downloads
für beide Artifact-Typen. Plan:
`.claude/plan/2026-08-19-1700_tabellen-ui-und-exporte.md`.

- **Export-Endpoints:** `GET /wa-tables/{id}/export?format=csv|xlsx` und
  `GET /wa-artifacts/{id}/export?format=markdown|html` — Muster
  `routers/_export.py` (ADR-0032): `attachment`, Lesen für Viewer offen,
  `write_limit` als Rate-Limit. Store-Lesepfad `TableStore.read_table_rows`
  (SQL-Bau im Store, ARC-3; explizite Katalog-Spalten — interne
  Store-Spalten bleiben draußen); `EXPORT_ROW_LIMIT = 10_000`, darüber 413
  statt stillem Teil-Export. Renderer in `wa_render.py`: `render_table_xlsx`
  (openpyxl, MIT-lizenziert, Formel-Guard aus derselben Quelle wie CSV),
  `render_artifact_export_markdown` (YAML-Frontmatter),
  `render_artifact_export_html` (MarkdownIt `html: False` wie
  `agent_render_service`, Meta-CSP im Dokument — sanktionierte Ausnahme von
  der Rohtext-Regel der Web-UI, s. ADR-0047-Nachtrag 2026-08-19).
- **Security-Review:** 5 Findings, alle behoben — XLSX-Rendering blockierte
  den Event-Loop (`asyncio.to_thread` + `write_limit`), XML-illegale
  Steuerzeichen brachen den XLSX-Export von Bestandsdaten (Schreibpfad jetzt
  422, Renderer strippt zusätzlich), Frontmatter-Injection über
  `source_system`/`source_url` (`single_line`), Meta-CSP + `no-referrer`
  gegen Tracking beim `file://`-Öffnen, Formel-Guard prüft auf getrimmter
  Kopie (Google Sheets trimmt beim Import). Details: ADR-0047-Nachtrag
  2026-08-19.
- **Web:** Tabellen-Tab in der Area-Detailseite (in BEIDEN Zweigen — private
  Agent-Areas hatten bislang gar keine Tabs), neue TableDetailPage (Schema,
  Konventionen, Vorschau der neuesten 50 Zeilen, Export-Dropdown CSV/Excel),
  Hooks `useWaTables`/`useWaTable`. Notizen-Export in der ArtifactDetailPage
  (Markdown-/HTML-Download plus „Als PDF drucken" via `window.print` und
  eigenem Print-Stylesheet).
- **User-Entscheidungen (bindend):** CSV + echtes `.xlsx` (openpyxl
  genehmigt); PDF über Browser-Druck statt Server-PDF (keine schwere
  Dependency). Details/Alternativen: DECISIONS.md 2026-08-19.
- **Info-Befund I-1 (bewusst offen):** der Export zählt bis zu 10 000 Zeilen
  als EIN `agent_access_log`-Eintrag bzw. eine Kontingent-Einheit — das
  Volumen wird untererfasst.
- **DoD:** Python 1698 Tests grün, Coverage-Gate erfüllt; Web 986 Tests grün
  (13 neu, inkl. a11y je Tab), Coverage 86,3/80,3/82,5/87,2 (Floors
  80/79/75/80), tsc/lint/build grün.

### Refactoring-Lauf Web-Dedup: Status-/Entity-Aktionen (2026-08-19)

Hotspot-getriebener Lauf (Playbook Refactoring-Lauf; Churn × Komplexität,
jscpd, radon): Python nach den Aufräum-Stufen 1–3 zahm (max. C-16), der
messbare Tech-Debt lag in per-Feature-Kopien der Web-UI. Plan:
`.claude/plan/2026-08-19-1805_refactor-web-dedup-status-actions.md`.

- **Welle 1:** 4× `StatusActionBar` + 5× Status-Lib-Kopien →
  `components/version/` (StatusActionBar mit `onTransition`-Callback,
  State-Machine in `versionStatus.ts`, i18n `common.statusBar.*`).
  Nebenfund: die Personas-/Playbooks-Bars wurden nie gerendert (tote
  Komponenten); beide Seiten haben eigene Inline-Transition-Logik —
  Kandidat für einen Folgelauf.
- **Welle 2:** 11 Button-Kopien (Delete ×4, Export ×4, Duplicate ×3) →
  `components/entity/{EntityDeleteButton,EntityExportButton,
  EntityDuplicateButton}`; entity-spezifische Texte als Props, testids
  unverändert. Bewusst ausgelassen: `SystemPromptStatusActionBar`,
  Agents-/Feedback-Buttons (abweichendes Verhalten).
- **Metriken:** jscpd 2,94 % → 2,47 % (Code-Dup-Zeilen 2073 → 1510,
  Ziel-Cluster 0 Clone-Paare); Netto −2298 Zeilen über 54 Dateien.
  Design-Weiche in DECISIONS 2026-08-19 (User-Entscheidung Option A).
- **Bewusst ausgelassen (Folgelauf mit DB-Umgebung):** Python-Service-
  Duplikate (`persona_service ↔ resource_service` u. a.) und
  `workspace_repository.py` — das Sicherheitsnetz ist DB-gebunden und in
  der Cloud-Session ohne Postgres nicht lokal ausführbar.
- **DoD:** eslint 0 Errors, tsc + `tsc -b` (Build) grün, 956 Vitest grün,
  Coverage 86,50/80,61/82,44/87,50 (Floors 80/79/75/80).

### Repo-Pflege: Branch-Hygiene + Dependabot + E2E-Spitze (2026-08-19/20)

Plan: `.claude/plan/2026-08-19-2110_repo-pflege-branches-tests.md` (PR #387).

- **Branch-Hygiene:** 81 Remote-Branches klassifiziert — 70 tot (22 per
  Merge-Commit enthalten, 48 mit gemergtem Squash-/Inhalts-PR bzw. ohne
  Delta), 9 aktiv (offene PRs/Dependabot), 1 Restliste
  (`claude/autonomous-code-agent-setup-4fk7ed`, PR #336 closed-unmerged).
  Löschung aus der Cloud-Session nicht möglich (Git-Proxy erlaubt nur den
  Arbeits-Branch) → fertiger Lösch-Befehl liegt beim Owner; Empfehlung:
  GitHub-Setting „Automatically delete head branches" aktivieren (#338).
- **Dependabot:** #368 (Web-minor-patch, 28 Pakete) lokal voll verifiziert
  und gemergt; #245/#243/#242 geschlossen (Juni-Basen mit
  Lockfile-Konflikten; #242 zudem Major-Bump → bewusster eigener PR);
  #384 offen: funktional grün, aber der Ruff-Bump erzeugt Format-Drift in
  5 Dateien → Bump+Reformat in einem Schritt nötig (PR-Kommentar);
  #330/#240 (Actions-Bumps) warten auf lebende CI.
- **E2E-Spitze (ADR-0041 Phase 4) scharf:** die vier fixme-Journeys sind
  implementiert — `e2e/helpers/auth.ts` (Signup mit Autoconfirm,
  Session-Injektion via `sessionStorage['who2be.auth.session']`,
  Lazy-Workspace-Seed über `GET /v1/me`), Journeys Persona-Lifecycle,
  Playbook→Resource-Block-Ref-Backlink, Agent-Read-Active (REST-Äquivalent
  zu MCP-`get_persona`, im Spec begründet), Invitation-Accept inkl.
  Email-Mismatch-Guard; minimale `data-testid`-Anker (branch-action-*,
  tab-*, used-by-item-*, error-alert u. a.). Der CI-e2e-Job bleibt
  Soft-Gate — Härtung erst nach grünem CI-Beleg; ein echter
  Playwright-Lauf steht aus (CI-Infra bricht weiterhin nach ~4 s ab, #338;
  lokal kein Docker).
- Lokale DoD auf dem PR-#387-Head (inkl. gemergtem #368): eslint 0 Errors,
  tsc + gezielter e2e-Typ-Check grün, 956 Vitest, Coverage
  86,50/80,61/82,44/87,50, Build grün.

### Repo-Pflege: Doku & Struktur (2026-08-20) — gemergt (PR #389)

Playbook-Lauf über beide Tracks; Plan
`.claude/plan/2026-08-20-0813_repo-pflege-doku-struktur.md`. Vier Weichen
per User-Entscheidung (alle Empfehlungen bestätigt): Public-Artefakte jetzt
komplett Englisch; OpenAPI-Export ohne CI-Gate; docs-Index statt
Diataxis-Umbau; Community-Health Stufe 2.

- **Public-Artefakte englisch + aktuell:** README (mit CI-/License-Badges,
  WorkArea-Achse in Features/Architektur), CHANGELOG (August-Blöcke
  nachgezogen: WorkArea/KB/Tabellen, semantische Suche, Exporte, Fixes,
  Security-Härtung), CONTRIBUTING, SECURITY, ROADMAP — Übersetzung und
  Inhalts-Update in einem Zug.
- **Neu:** `.github/ISSUE_TEMPLATE/` (Bug/Feature als YAML-Forms +
  config.yml mit Security-/Support-Kontaktlinks), `SUPPORT.md`,
  `docs/README.md` (Index nach Diataxis-Typ + Zielgruppe),
  `docs/reference/openapi.json` (140 Pfade) + `scripts/export_openapi.py`.
- **`.github/PROJECT.md`** vom erledigten Externe-Tools-Vorhaben auf
  „Public-Switch & erstes Release" (#338–#341) umgestellt.
- **Negativ-Listen-Scan sauber** (Tree; History-Beleg gitleaks 2026-07-22).
- **Verify:** Issue-Form-YAML validiert, Link-Check über alle geänderten
  Dateien grün, CHANGELOG-Kategorien konform, ruff/format/mypy fürs neue
  Skript grün, OpenAPI-Export tatsächlich ausgeführt.
- **Owner-Punkte (nicht aus der Session setzbar):** Repo-Description +
  Topics (Textvorschläge im PR), Screenshot/GIF als visueller Anker im
  README, ggf. Discussions aktivieren, Social-Preview-Bild.

### Repo-Pflege: Status-Nachführung & Abhaken (2026-08-20, 2. Lauf)

Kleiner Pflege-Lauf auf User-Auftrag; Plan (inkl. Gap-Report und
vollständiger Zusammenfassung der offenen Aufgaben):
`.claude/plan/2026-08-20-1031_repo-pflege-status-abhaken.md`.

- **Status-Tracking nachgeführt:** `.claude/plan/README.md` um die Zeilen
  der Läufe 2026-08-19-1805 (Refactoring Web-Dedup), 2026-08-19-2110
  (Branch-Hygiene/E2E, PR #387), 2026-08-20-0813 (Doku & Struktur, PR #389)
  ergänzt — die Übersicht war drei Läufe hinterher.
- **Issue #338 O1: erst abgehakt, dann revidiert** — beim Abhaken galt der
  Stand „CI-Gate aktiv seit 2026-08-16"; der CI-Lauf auf PR #390 deckte
  auf, dass die Infra-Regression seit 2026-08-19 ~16:37 zurück ist (s.
  §Standards / CI). O1 wieder auf offen gesetzt, Befund im Issue
  dokumentiert; O2–O4 bleiben Owner-Schritte.
- **Abhak-Prüfung #341:** WP-8 offen (`version = "0"`, kein Tag), WP-9
  teilerledigt (Journeys scharf, aber `continue-on-error` steht noch und
  der CI-Grün-Nachweis auf einem Release-Commit fehlt), WP-10 offen —
  keine Checkbox setzbar.
- Public-Doku ohne Stale-Fund (Stand PR #389, heute gemergt);
  Negativ-Listen-Scan sauber.

### Offene Aufgaben abarbeiten (2026-08-20, 3. Lauf — PR #390)

Code-Task-Flow über die codebaren offenen Aufgaben; Plan (inkl.
Owner-Schrittfolge Teil B):
`.claude/plan/2026-08-20-1047_offene-aufgaben-abarbeiten.md`.

- **#385 behoben:** die 17 ERRORs ohne erreichbares Postgres verteilten sich
  auf ZWEI Dateien ohne `integration`-Marker —
  `test_resource_slug_children_duplicate.py` (5) und `test_external_tools.py`
  (12; im Issue nicht genannt, selbe Fehlerklasse). Fix: `pytestmark =
  pytest.mark.integration` je Modul; Repro vorher 17 ERRORs, nachher
  17 Skips.
- **#384 superseded:** die 8 Bumps der `python-minor-patch`-Gruppe (pytest
  9.1.1, mypy 2.3.1, ruff 0.16.3, fastapi 0.141.1, pydantic-settings 2.15.0,
  pypdf 6.16.1, redis 8.1.0, fastmcp 3.4.7) per `uv lock --upgrade-package`
  + Reformat in einem Schritt. Aufklärung des Format-Drifts: **Ruff 0.16
  formatiert Python-Codeblöcke in Markdown** — die „5 Dateien" sind
  `.md`-Dateien (4 Plan-/ADR-Dokumente + 1 Test-Run-Protokoll).
- **#341 WP-8 (Teil):** Root-`pyproject.toml` `version = "0"` → `0.1.0`
  (Workspace-Members standen schon auf 0.1.0). Tag + Release bewusst erst
  nach Merge + grünem CI-Lauf (Blocker #338 O1).
- **DoD (ohne DB/Docker in der Session):** ruff check + `ruff format
  --check` (697 Dateien) + mypy strict (449 Quellen) grün; **1315 pytest
  passed / 445 skipped** (DB-Integrationstests zentral geskippt);
  Coverage-Gate ist CI-Sache (Postgres-Service dort).

### UX-Backlog-Welle mit Sub-Agents (2026-08-20, Issues #391–#394)

Orchestrierter Lauf (Code-Task-Flow) über die Reste des Juni-UX-Backlogs
(`2026-06-27-1200`) + den STATE-Refactor-Kandidaten; Plan
`.claude/plan/2026-08-20-1115_ux-backlog-welle-subagents.md`. Inventur
vorab: System-Prompt-MCP-Tools, Tool-Anker (→ ADR-0043) und
Draft-on-Edit-Sichtbarkeit waren längst erledigt/überholt.

- **#391 StatusActionBar-Refactor:** Personas-/Playbooks-Detailseiten auf
  die zentrale Bar (neuer optionaler `labels`-Override, Testids
  `branch-action-*`, Promote-Suffix historisch `publish`), Button-/Toast-
  Texte unverändert (Neutralität via i18n-Textabgleich + unveränderte
  Label-Assertions). Dabei den E2E-Defekt behoben: die scharfen Journeys
  klickten Testids, die auf den Seiten nicht existierten. Befund:
  `BranchStatus`-`actions`-Zweig ist jetzt toter Code (Folge-Kandidat).
- **#392 MCP-Docstring-DX:** Modi-Schema (`create/update_persona`),
  kanonisches BlockNote-Body-/Pill-Format (`create/update_playbook`,
  `create/update_resource`), alles gegen die Pydantic-Modelle belegt;
  `tools/list`-Payload 127 KB < 160-KB-Budget; 241 mcp-Tests grün.
- **#393 Tag-Gruppierung:** Playbooks-Modus `tag` (Mehrfach-Tag-
  Zugehörigkeit, „Ohne Tag"-Gruppe), Resources erstmals mit Gruppierung
  (`features/resources/lib/grouping.ts`). Agent-/Persona-Gruppierung
  bewusst NICHT gebaut: List-Payloads tragen keine Verknüpfung — braucht
  Batch-Feld am List-Endpoint (sonst N+1), als Befund dokumentiert.
- **Rest des Juni-Plans:** Draft-Discard = erste Python-Aufgabe nach
  CI-Wiederbelebung (kein lokales Sicherheitsnetz ohne DB); Quick-Release
  widerspricht `TRANSITION_RULE_DOC` → Owner-Weiche; proaktive
  Pflichtfeld-Hinweise = Folgewelle.
- **#394 Policy-Presets (Welle 2):** Preset-Auswahl im Agent-Policy-Editor
  („Nur lesen" / „Editor ohne Freigabe" / „Editor mit Freigabe"), abgeleitet
  aus den 12 Write-Capability-Checkboxen (`lib/policyPresets.ts` als SSoT,
  pure functions), Abweichung zeigt „Benutzerdefiniert"; reine UI, kein
  Persistenz-Feld. Produkt-Nuance dokumentiert: der Default-Agent zeigt
  „Benutzerdefiniert", weil `feedback_write` per Default an ist —
  Owner-Feinschliff wäre, Feedback-Caps aus dem Preset-Scope zu nehmen.
- **Konsolidierungs-DoD (beide Wellen):** eslint 0 Errors, tsc grün, volle
  Suite **985 Vitest passed** (Coverage 86,61/80,99/82,6/87,63, Floors
  80/79/75/80), Build grün; mcp: 241 pytest grün.

## Bekannte Probleme

- **Tabellen-Store-Verzeichnisse überleben den Hard-Purge** (bewusst, WP20):
  `cleanup_deleted_area_stores` fasst nur Verzeichnisse an, deren Workspace
  noch existiert — Schutz gegen einen Purge-Lauf gegen die falsche/leere DB.
  Nach einem Org-/Workspace-Hard-Purge bleiben die SQLite-Dateien deshalb
  liegen und werden nur gemeldet (`unknown_store_dirs` + WARNING). Die
  Nachbereinigung ist ein dokumentierter Betreiber-Schritt (RUNBOOK
  §Tabellen-Store-Backup, Löschkonzept §4a) — kein automatischer Pfad.
- **Blob-Objekt-Sweep hat eine Scope-Lücke** (dokumentiert): Objekte werden je
  Workspace gesucht, der im `wa_blob`-Katalog vorkommt. Ein Workspace, dessen
  allererster Ingest scheitert, hat nie eine Katalog-Zeile — sein einzelnes
  Objekt bleibt liegen (Alternative wäre ein Bucket-Vollscan je Cron-Lauf).
- **`audit_log.detail`: Altzeilen bleiben doppelt JSON-kodiert** (Rest des
  Befunds von 2026-08-16): der Schreibpfad ist korrigiert
  (`$6::text::jsonb`), die BESTEHENDEN Zeilen werden bewusst nicht
  umgeschrieben — ein Audit-Trail wird nicht rückwirkend angefasst. Wer
  `detail` per SQL (`->>`) auswertet, muss für Altzeilen mit einem
  JSON-*String* rechnen. Dass dieselbe Fehlerklasse woanders einen Endpunkt
  gekillt hat, steht oben (§`describe_table` antwortete mit 500).
- Offene Owner-Entscheidungen: `docs/standards-review-2026-07-20.md` §4
  (ADR-0002 enforce vs. amend, Branch-Protection/Merge-Strategie,
  On-Prem-RLS, Cloud-Image-Deploy, LIC-1-Mechanik, coverage.all/E2E/CLA).

## Nächste Schritte (nicht-Code, manuell beim Owner)

Als Owner-Checkliste getrackt in Issue #338 (Welle 3 der Release-Mechanik
in #341):

1. ~~CI-Gate~~ ✅ (SHA-Pinning-Fix, s. o.) · ~~Public-Flip~~ ✅ 2026-08-20.
2. ~~Tag `v0.1.0` + GitHub-Release~~ ✅ 2026-08-20 14:45 UTC (Tag auf
   `main`, Notes aus dem CHANGELOG; künftige Releases per Actions →
   Release → „Run workflow").
3. GitHub-Settings-Rest: **Branch-Protection für `main`** (am 2026-08-21
   per API als `protected: false` gegengeprüft — real offen) und
   Merge-Strategie; **Description + Topics** setzen (Repo hat beides noch
   nicht; fertiger Text in #338 und PR #389). ~~Auto-delete head
   branches~~ ✅ aktiv, ~~Discussions~~ ✅ an; Secret-/Push-Protection und
   Private vulnerability reporting noch bestätigen, ggf. Social-Preview.
4. CLA-Assistant aktivieren (vor den ersten externen PRs) — #338 O3;
   `CONTRIBUTING.md` §CLA hält die Stelle für den Link bereit.
5. **Pflicht vor 1.0** (nicht mehr optional): Deploy-Verifikation
   (#341 WP-10). Braucht `DEPLOY_HOST` als Variable plus `DEPLOY_USER`/
   `DEPLOY_SSH_KEY`; solange sie fehlen, überspringt sich der Job still
   (`deploy.yml:80`) — die Pipeline war nie rot, aber auch nie verifiziert.

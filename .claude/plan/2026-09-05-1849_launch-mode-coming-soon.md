# „Coming soon"-Modus per `WHO2BE_LAUNCH_MODE` (#429)

- Status: **in Arbeit**
- Datum: 2026-09-05, 18:49 UTC
- Issue: #429 (`agent-ready`, `size/S`) — harte Abhaengigkeit fuer #454
- Warteschlange: Platz 1 in #442, Welle 1
- Norm: Ask-Once-Gate bestanden (vier Pflichtfelder + sieben vorentschiedene
  Weichen stehen im Issue-Body); dieser Plan wiederholt sie nicht, sondern
  verweist darauf.

## 1. Outcome

Eine einzige Env-Variable `WHO2BE_LAUNCH_MODE=open|coming_soon` (Default `open`)
schaltet die App in den „bald verfuegbar"-Modus: `/signup` zeigt eine
Hinweisseite (DE/EN), Registrierung ist auch per direktem GoTrue-Request
geblockt, waehrend Login, Passwort-Reset, Magic-Link-Einladungen und
`/oauth/consent` unveraendert funktionieren. Umschalten ohne Rebuild.

## 2. Muster-Entscheidung

**Keine Muster-Entscheidung noetig.** Die Aenderung erweitert zwei bereits
bestehende Strukturen, ohne eine neue Abstraktion einzuziehen:

- `RuntimeConfig` / `Config` in `apps/web/src/config.ts:25-43` — das Paar aus
  optionalem Runtime-Wert und aufgeloestem Pflichtwert existiert dort bereits
  fuer vier Schluessel (`apiBaseUrl`, `mcpUrl`, `supabaseUrl`, `supabaseAnonKey`)
  plus `signupDisabled`. `launchMode` und `launchContact` folgen demselben
  Muster; das ist der von aussen gesetzte Vertrag (`/config.js`), keine Wahl.
- Das Gate sitzt an der bestehenden Stelle `SignupPage.tsx:70-78`, wo heute
  schon `config.signupDisabled` ausgewertet wird — kein zweiter Gate-Ort in
  `routes.tsx` (Weiche 4 des Issues).

Eine Abstraktion ueber „Launch-Modi" (Strategy o. ae.) waere die kompaktere
Alternative *nicht* — sie waere die groessere: es gibt genau zwei Werte und
einen Konsumenten. Die Variabilitaets-Schwelle (drittes Vorkommen bzw. zweiter
existierender Fall) ist nicht erreicht.

## 3. Arbeitspaket — ein Paket, ein Sub-Agent

Das Feature ist zusammenhaengend (eine Konfig-Kette vom Compose-Env bis zur
gerenderten Seite) und laesst sich nicht sinnvoll datei-disjunkt schneiden.
Also **ein** Sub-Agent, kein Fan-out.

**Modell-Wahl: Sonnet.** Das Issue trifft alle sieben Design-Weichen vorab und
nennt die Einstiegspunkte als `datei:zeile`; es bleibt Ausfuehrung eines klar
umrissenen Pakets, keine Entwurfsarbeit. Hochstufen nur, wenn ein zweiter Lauf
noetig wird.

### Dateien (aus Scope „In" des Issues)

`apps/web/src/config.ts` (+ `config.test.ts`) · `apps/web/docker/40-who2be-runtime-config.sh` ·
`apps/web/src/features/auth/pages/{SignupPage,LoginPage,ComingSoonPage}.tsx`
(+ Tests, + `ComingSoonPage.a11y.test.tsx`) ·
`apps/web/src/i18n/locales/{de,en}.json` (nur Namespace `auth`) ·
`.env.example` · `deploy/hetzner/.env.example` · `deploy/hetzner/RUNBOOK.md` ·
`docs/signup-and-invites.md` · `scripts/smoke.sh` · `CHANGELOG.md`

### Nicht anfassen

`Caddyfile`; Einladungs- und Consent-Routen; `GOTRUE_DISABLE_SIGNUP` aus Compose
entfernen; neue API-Endpunkte; eine Build-Time-Variante des Modus
(`VITE_WHO2BE_LAUNCH_MODE`); `docs/frontend/**` ausser Lesen; alles unter
`apps/api/`, `apps/mcp/`, `packages/`.

### Fallstricke, die aus dem gelesenen Code folgen

- `40-who2be-runtime-config.sh` hat eine `sanitize()`-Funktion, weil die Werte
  unescaped in ein JS-String-Literal laufen. `launchMode` und `launchContact`
  sind Strings und **muessen** durch `sanitize` — anders als das boolesche
  `signupDisabled`, das ueber einen `[ … ] && echo true` -Zweig geschrieben wird.
- `signupDisabled` wird in `config.ts:118-120` per `??` aus Runtime **oder**
  Build-Env aufgeloest. Die Rueckwaertskompatibilitaet aus Weiche 2(a) gehoert
  genau dorthin: `coming_soon` ODER Alt-Schalter ⇒ `signupDisabled` wahr.
- Unbekannter `launchMode`-Wert ⇒ `open` + `console.warn` (Weiche 7). Fail-open
  ist Absicht; die harte Sperre liegt bei GoTrue.
- Lint-Gate: direkte `<a>` in `features/**` sind ESLint-`error` — externer
  Kontakt-Link ueber `buttonVariants`/`asChild` (CLAUDE.md §Lint-Gates).

## 4. Verifikation (exakt aus dem Issue, CI-identisch)

```bash
cd apps/web && npm run lint && npx tsc -b && npm run test:coverage && npm run test:a11y && npm run build
```

Gruen heisst: Exit 0 ueberall; Vitest-Thresholds (statements 80 / branches 79 /
functions 75 / lines 80) halten; i18n-Paritaet DE/EN im Namespace `auth`.

Der Compose-Smoke und die GoTrue-`422`-Probe aus dem Issue brauchen einen
laufenden Stack; ob sie in dieser Umgebung fahrbar sind, entscheidet sich beim
Lauf und wird hier nachgetragen — nicht behauptet.

## 5. Branch-Abweichung

Die DoD des Issues nennt `feat/launch-mode-coming-soon`. Die Session-Vorgabe
dieses Laufs erlaubt Pushes ausschliesslich auf `claude/upbeat-mayer-506f7s`;
die Arbeit landet deshalb dort. Als Kommentar an #429 vermerkt.

**Nachtrag 19:20 UTC:** PR #455 (Backlog-Aufbereitung) ist gemergt, der Branch
damit auf gemergter Historie. Er wurde auf den aktuellen `main` vorgezogen
(Fast-Forward, `57810ef` ist Vorfahr von `b95048a`); #429 bekommt einen
**eigenen** PR statt sich auf abgeschlossene Arbeit zu stapeln.

`main` traegt seither zusaetzlich PR #456 aus einem Parallellauf — dieselbe
Backlog-Aufbereitung, auf dem gemergten Stand aufgesetzt. Er hat die
Entscheidung „#427 vor dem blockierten #436" uebernommen und abweichend **#438
vorgezogen** (Lesart der Owner-Vorgabe „nach dem Cloud-Block": direkt danach
statt ans Listenende). Beide Lesarten sind vertretbar; seine Fassung bleibt
stehen. Fuer #429 aendert das nichts — es steht in beiden Fassungen auf Platz 1.

## 6. Konsolidierung (Phase 3.5)

Der Sub-Agent meldete alle fuenf Kommandos gruen. Geprueft wurde trotzdem der
Diff, nicht die Zusammenfassung — mit einem Ergebnis, das die Meldung
relativiert.

### Der Fund, der das Paket sonst wirkungslos gelassen haette

`docker-compose.yml` und `deploy/hetzner/who2be/docker-compose.yml` reichten
`WHO2BE_LAUNCH_MODE`/`WHO2BE_LAUNCH_CONTACT` **nicht** an den `web`-Container
durch. Das Muster daneben (`docker-compose.yml:184`,
`deploy/hetzner/who2be/docker-compose.yml:143`) tut das fuer
`WHO2BE_SIGNUP_DISABLED` seit jeher. Ohne die Zeilen haette der Entrypoint den
Wert nie gesehen und `/config.js` immer `launchMode: "open"` geschrieben:
Akzeptanzkriterium 3 („Env aendern + `docker compose up -d` genuegt") waere
unerfuellbar gewesen, obwohl alle Tests gruen sind.

Der Sub-Agent hat den Fund korrekt gemeldet und korrekt **nicht** selbst
behoben — die Compose-Dateien standen nicht in seiner Datei-Liste. Die Luecke
lag im Zuschnitt: das Issue listet unter Scope „In" jede Doku-Datei, aber nicht
die Env-Weiterleitung, ohne die das Feature nicht wirkt. Vom Orchestrator
nachgezogen (zwei Zeilen je Datei, dem Nachbarn nachgebildet; triviale
Aenderung ohne Design-Entscheidung).

**Lehre fuer kuenftige Zuschnitte:** eine Scope-Liste, die den Konsumenten einer
neuen Env-Variablen nennt, aber nicht ihren Transportweg, ist unvollstaendig.

### Verifikation — selbst gefahren

| Kommando | Ergebnis |
|---|---|
| `npm run lint` | 0 Errors, 64 Warnings (alle vorbestehend, `react-hooks/set-state-in-effect` in `hooks/use*.ts`) — Exit 0 |
| `npx tsc -b` | keine Ausgabe — Exit 0 |
| `npm run test:coverage` | 183 Dateien, **1038 Tests passed** — Exit 0 |
| `npm run test:a11y` | 48 passed, 990 skipped — Exit 0 |
| `npm run build` | `built in 2.15s` (nur der bekannte Chunk-Size-Hinweis) — Exit 0 |

Coverage: Statements 86.52 % · **Branches 81.12 %** · Functions 82.05 % ·
Lines 87.55 % — gegen die Schwellen 80 / 79 / 75 / 80.

Zusaetzlich selbst geprueft, weil Shell-Logik von Unit-Tests nicht erfasst wird
— die Wahrheitstabelle des Entrypoints ueber alle sechs Env-Kombinationen:

| `WHO2BE_LAUNCH_MODE` | `WHO2BE_SIGNUP_DISABLED` | `signupDisabled` | `launchMode` |
|---|---|---|---|
| `open` | true | `true` | `"open"` |
| `open` | false | `false` | `"open"` |
| `coming_soon` | true | `true` | `"coming_soon"` |
| `coming_soon` | **false** | **`true`** | `"coming_soon"` |
| _(leer)_ | true | `true` | `"open"` |
| _(leer)_ | false | `false` | `"open"` |

Zeile 4 ist der Beleg fuer Weiche 2a: der Modus zieht `signupDisabled` allein
hoch. Beide Compose-Dateien wurden zusaetzlich per `yaml.safe_load` geparst.

### Uebergabe-Bericht (Phase 4.1)

**(a) Betroffene Elemente** — mit `ripgrep` rueckwaerts gesucht, nicht erzaehlt:

- **DIREKT (4 Fundstellen in 3 Dateien):** `SignupPage.tsx:74` (`launchMode`),
  `SignupPage.tsx:80` (`signupDisabled`), `LoginPage.tsx:280` (beide),
  `ComingSoonPage.tsx:16` (`launchContact`).
- **TRANSITIV:** keine. `config` ist zwar ein modulweites Singleton mit vielen
  Importeuren, aber die **geweitete `signupDisabled`-Semantik** (jetzt auch wahr
  bei `coming_soon`) erreicht ausschliesslich die zwei Stellen oben — beide sind
  angepasst. Kein dritter Leser erbt sie still. Das war die eigentliche
  Risikofrage dieses Diffs.
- **VERMUTET (Laufzeit-Verdrahtung, statisch nicht sichtbar):** die Kette
  Compose-Env → `40-who2be-runtime-config.sh` → `/config.js` →
  `window.__WHO2BE_CONFIG__`, sowie `scripts/smoke.sh`, das
  `WHO2BE_LAUNCH_MODE` aus der Host-Umgebung liest. Die Shell-Haelfte ist ueber
  die Wahrheitstabelle oben belegt; die Container-Haelfte nicht — siehe
  Rest-Test-Liste.

**(b) Rest-Test-Liste:** In `config.ts`, `ComingSoonPage.tsx`, `SignupPage.tsx`
und `LoginPage.tsx` ist **jede** Funktion von Tests ausgefuehrt (`f`-Map der
v8-Coverage: 6/6, 1/1, 10/10, 10/10 — keine ungedeckte Funktion). Es bleibt
keine namentliche Luecke auf Funktionsebene.

Nicht automatisiert geprueft und deshalb manuell nachzuholen:

1. **Akzeptanzkriterium 1 gegen einen echten Stack** — `docker compose up -d`
   mit `WHO2BE_LAUNCH_MODE=coming_soon` + `GOTRUE_DISABLE_SIGNUP=true`, dann
   `/signup` im Browser und `curl` gegen `/auth/v1/signup` (erwartet `422`).
   Die Unit-Tests belegen die Logik, nicht die Verdrahtung durch den Container.
2. **Akzeptanzkriterium 4** — `bash scripts/smoke.sh` einmal in beiden Modi:
   im `open`-Modus darf die Probe nicht laufen, im `coming_soon`-Modus muss sie
   bei fehlendem `GOTRUE_DISABLE_SIGNUP` abbrechen.
3. **Darstellung der Hinweisseite bei 375 px** (Sichtpruefung; Mobile-E2E kommt
   mit #431).

### Nebenfunde (nicht gefixt)

- `.env.example` beschrieb `VITE_WHO2BE_SIGNUP_DISABLED` als den aktuellen Weg,
  obwohl die Runtime-Config-Migration laengst `WHO2BE_SIGNUP_DISABLED` nutzt.
  Beim Neuschreiben der Sektion mit korrigiert (im Scope, da dieselbe Datei).
- 64 vorbestehende Lint-Warnungen `react-hooks/set-state-in-effect` in
  `apps/web/src/hooks/use*.ts` — unveraendert, ausserhalb des Scope.

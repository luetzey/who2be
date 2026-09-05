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

## 6. Offen / nachzutragen

- Ergebnis des Verifikations-Laufs
- Uebergabe-Bericht (betroffene Elemente, Diff-Coverage, Test-Gaps)
- Nebenfunde

# „Angemeldet bleiben (12 h)" (Issue #430)

- Status: **in Arbeit**
- Datum: 2026-09-05, 22:55 UTC (26. Lauf)
- Issue: #430 (`agent-ready`, `size/S`)

## 1. Ask-Once-Gate

**Bestanden.** Outcome, sechs Akzeptanzkriterien, Out-of-Scope, Verifikations-
Kommandos und **zehn** vorentschiedene Weichen stehen im Body — das
gruendlichste Issue der Warteschlange.

## 2. Weiche 6 vorab beantwortet (im Issue als „zu verifizieren" markiert)

Die Frage war, ob auth-js 2.112.3 mit `localStorage` den `SIGNED_OUT`-Event
cross-tab liefert, oder ob ein `window.addEventListener('storage', …)` noetig
ist. **Weder noch — auth-js bringt einen `BroadcastChannel` mit, und die
Bedingung dafuer ist heute schon erfuellt:**

```js
// apps/web/node_modules/@supabase/auth-js/dist/main/GoTrueClient.js:256
if (isBrowser() && globalThis.BroadcastChannel && this.persistSession && this.storageKey) {
    this.broadcastChannel = new globalThis.BroadcastChannel(this.storageKey);
```

`supabase.ts:30` setzt `persistSession: true`, `:34` setzt
`storageKey: 'who2be.auth.session'`. Der Kanal existiert also unabhaengig vom
Storage-Backend — der Wechsel auf `localStorage` aendert daran nichts.

**Folge:** Cross-Tab-Logout (AC 3) muss nicht gebaut, sondern nur **belegt**
werden. Kein `storage`-Listener, kein eigener `BroadcastChannel`. Damit
entfaellt auch die Eskalationsbedingung „wenn Cross-Tab-Logout nur mit einem
BroadcastChannel > ~100 Zeilen erreichbar ist".

Einschraenkung, die in die Doku gehoert: ein `BroadcastChannel` erreicht nur
**gleichzeitig offene** Tabs. Ein Tab, der waehrend des Logouts geschlossen war,
merkt beim naechsten Oeffnen nichts davon — dort greift die Ablauf-Pruefung aus
Weiche 5 (`signed_in_at` gegen die Obergrenze).

## 3. Muster-Entscheidung

**Delegierender Storage-Adapter** (Weiche 4, im Issue entschieden): ein Adapter
in `lib/supabase.ts` liest das Flag `who2be.auth.remember` und routet Reads und
Writes nach `localStorage` bzw. `sessionStorage`.

Kompaktere Alternative, gegen die das Issue entschieden hat: zwei Clients oder
ein `createClient`-Neuaufbau beim Umschalten. **Beleg fuer die Variabilitaet:**
`createClient` bindet den Storage einmalig auf Modulebene (`supabase.ts:28-37`)
— ein zweiter Client waere eine zweite Quelle fuer denselben Zustand.

Der Adapter ist damit keine neue Abstraktion, sondern die Erweiterung des
bereits vorhandenen `sessionStorageAdapter` um eine Fallunterscheidung.

## 4. Was dieses Paket besonders macht

**Es revidiert eine akzeptierte ADR.** `docs/adr/0035-web-session-storage-tradeoff.md`
hat `sessionStorage` genau deshalb gewaehlt, weil eine persistente Ablage die
XSS-Angriffsflaeche vergroessert. Ein DECISIONS-Eintrag genuegt dafuer nicht —
es braucht **ADR-0052**, die ADR-0035 auf „Abgeloest" setzt und die neue
Abwaegung traegt. Zwei widersprechende ADRs im Repo waeren der teuerste Ausgang.

**Der Security-Review ist Pflicht** (Weiche 8), Anker ist
`docs/standards-review-2026-07-08.md:51` §SEC-2. Liefert er einen Befund
≥ Medium, ist das eine Owner-Entscheidung — nicht still zu fixen.

## 5. Verifikations-Grenze

Die E2E-Journey (AC 1, „neuer Tab bleibt eingeloggt") braucht den
Compose-Stack. **In dieser Session ist kein Docker verfuegbar**, sie ist lokal
also nicht fahrbar. Anders als bei #453 ist das kein Blocker: der `e2e`-Job der
CI faehrt sie scharf, und Session-Verhalten ist nicht editions-abhaengig. Im PR
wird das offengelegt statt abgehakt.

Lokal vollstaendig pruefbar: lint, `tsc -b`, `test:coverage`, `test:a11y`,
`build` — und damit alle Vitest-Pfade der Akzeptanzkriterien.

Baseline (25. Lauf): 1063 Tests, Coverage 86,76 / 81,44 / 82,34 / 87,78.

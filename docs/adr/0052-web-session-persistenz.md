# ADR-0052 — Web-Session-Persistenz: opt-in "Angemeldet bleiben" mit absoluter Obergrenze

- Status: Akzeptiert (loest ADR-0035 ab)
- Datum: 2026-09-05
- Kontext: Issue #430 — der 2FA-Prompt pro Tab ist die groesste
  Alltagsreibung der App; die Sperre soll gelockert werden, ohne die
  Security-Doku unehrlich zu machen.
- Bezug: ADR-0035 (Web-Session im `sessionStorage`, hiermit abgeloest),
  ADR-0006 (Auth: Supabase-JWT + API-Token), `docs/mfa-admin.md`
  (Login-Step-up), `docs/standards-review-2026-07-08.md:51` §SEC-2
  (fortgeschrieben in `docs/standards-review-2026-07-20.md:122`).

## Kontext

ADR-0035 legt die Supabase-GoTrue-Session (Access-/Refresh-Token) bewusst in
`sessionStorage`: Tab-Lifetime statt Disk-Persistenz, weil eine dauerhafte
Ablage die XSS-Angriffsflaeche vergroessert (jeder gleichzeitig offene Tab UND
jeder kuenftige Tab nach einem Neustart waere betroffen, nicht nur der eine
laufende Tab). Diese Abwaegung war — und bleibt — korrekt fuer den Default.

Das Rest-Risiko aus ADR-0035 ist im Alltag jedoch teuer: jeder neue Tab und
jeder Browser-Neustart verlangt einen vollen Login **inklusive** TOTP-Step-up
(`docs/mfa-admin.md`, Login-Step-up). Bei mehreren gleichzeitig genutzten Tabs
(uebliches Nutzungsmuster dieser App) ist das die groesste taegliche Reibung.

## Entscheidung

**Opt-in Persistenz mit absoluter Obergrenze, Haken standardmaessig aus.**

1. **Checkbox "Angemeldet bleiben ({{stunden}} h)" auf der Login-Seite,
   default UNCHECKED.** Ohne Haken aendert sich nichts: die Session bleibt in
   `sessionStorage`, exakt das ADR-0035-Verhalten (Tab-Lifetime, voller Login
   inkl. 2FA in jedem neuen Tab).
2. **Mit Haken wandert NUR diese eine Session in `localStorage`** (ein
   delegierender Storage-Adapter in `lib/supabase.ts` routet pro Zugriff
   anhand eines separaten Flags — keine zwei Supabase-Clients, siehe
   Konsequenzen). Sie ueberlebt neuen Tab und Browser-Neustart.
3. **Absolute Obergrenze, clientseitig durchgesetzt:**
   `WHO2BE_SESSION_MAX_AGE_HOURS` (Runtime-Config, Default 12, Bereich 1-24,
   ungueltige Werte fallen fail-closed auf 12 zurueck). Die Pruefung sitzt im
   `SessionProvider` (Vergleich gegen einen beim Login gesetzten Zeitstempel im
   `localStorage`); sie ist bewusst KEINE Verkuerzung der serverseitigen
   Token-Lebensdauer (`GOTRUE_JWT_EXP`, Refresh-Rotation bleiben unveraendert,
   siehe Konsequenzen). Fuer einen normalen Nutzer ist die Grenze damit nicht
   verlaengerbar; gegen einen Angreifer, der das Token-Paar bereits besitzt,
   ist sie **keine** Schranke (§Konsequenzen, Negativ).
4. **Nach Ablauf: voller Login inklusive Step-up**, keine Ausnahme — die
   abgelaufene Session wird per `supabase.auth.signOut()` serverseitig
   invalidiert (Refresh-Token wird ungueltig), nicht nur lokal verworfen.
5. **Logout meldet alle offenen Tabs ab.** `@supabase/auth-js` eroeffnet
   bereits heute einen `BroadcastChannel` auf dem `storageKey`, sobald
   `persistSession: true` UND `storageKey` gesetzt sind (beides gilt seit
   ADR-0035 unveraendert) — kein eigener Listener/`BroadcastChannel` im
   who2be-Code noetig, siehe `lib/supabase.test.ts`. Einschraenkung: ein
   `BroadcastChannel` erreicht nur GLEICHZEITIG offene Tabs; ein waehrend des
   Logouts geschlossener Tab merkt beim naechsten Oeffnen nichts davon — dort
   greift stattdessen Punkt 3/4 (die Ablaufpruefung beim Boot).

## Warum das die XSS-Abwaegung aus ADR-0035 nicht unehrlich macht

ADR-0035s Kernpunkt bleibt wahr: **jede** persistente Ablage vergroessert die
XSS-Angriffsflaeche gegenueber Tab-Lifetime-`sessionStorage`. Diese ADR
verkleinert die Flaeche nicht, sie **grenzt sie ein und macht sie sichtbar
opt-in**, statt sie fuer alle Sessions gleichermassen zu akzeptieren:

- **Default bleibt das ADR-0035-Niveau.** Ohne aktiven Klick des Nutzers
  aendert sich am Rest-Risiko nichts — die neue Flaeche existiert nur fuer
  Sessions, die der Nutzer explizit dafuer markiert hat.
- **Zeitlich begrenzt statt unbefristet — im regulaeren Betrieb.** ADR-0035s
  Alternative B (`localStorage` ohne Grenze) wurde dort explizit "verworfen";
  diese ADR waehlt nicht B, sondern B mit einer Kappung: der regulaer
  benutzte Browser verwirft die Session nach `sessionMaxAgeHours` und
  invalidiert das Refresh-Token dabei serverseitig (`signOut()`), statt es
  nur lokal zu vergessen. **Das ist eine Begrenzung des Normalbetriebs, keine
  Schranke gegen einen Angreifer:** ausgeloest wird sie vom Client, und wer
  das Token-Paar aus dem `localStorage` getragen hat, fuehrt diesen Client
  nicht aus. Fuer diesen Fall bleibt allein die GoTrue-eigene
  Token-Lebensdauer wirksam — die Kappung verkuerzt das Zeitfenster fuer
  *stehengelassene* Sessions, nicht fuer *entwendete* (s. Konsequenzen,
  Negativ).
- **CSP bleibt die tragende Abwehr, unveraendert.** Die zentrale CSP in Caddy
  (F-12) ist weiterhin die primaere Verteidigung gegen XSS selbst — diese ADR
  aendert daran nichts; sie aendert nur, wie lange ein *erfolgreicher* XSS
  etwas Wertvolles vorfindet.
- **Es bleibt ein bewusst akzeptiertes Rest-Risiko, kein geloestes Problem.**
  Der Trigger-fuer-Re-Visit aus ADR-0035 (ein Auth-BFF mit `httpOnly`-Cookies)
  gilt unveraendert fort und wuerde auch diese ADR ersetzen.

## Konsequenzen

**Positiv**

- Beseitigt die groesste taegliche Reibung (2FA pro Tab) fuer Nutzer, die das
  bewusst in Kauf nehmen wollen, ohne den Default fuer alle zu verschlechtern.
- Die absolute Obergrenze ist Runtime-Config (`WHO2BE_SESSION_MAX_AGE_HOURS`)
  — Betreiber koennen sie ohne Rebuild auf ihr Risikoprofil einstellen
  (1-24 h), koennen sie aber NICHT ueber 24 h hinaus oder ganz abschalten.
- Cross-Tab-Logout kommt "kostenlos" aus `@supabase/auth-js` — kein
  zusaetzlicher Code, kein zusaetzlicher Zustand.
- `GOTRUE_JWT_EXP` und die Refresh-Token-Rotation bleiben unangetastet; die
  serverseitigen aal2-Gates (`require_aal2`) sind von dieser ADR nicht
  beruehrt — sie pruefen weiterhin jede Admin-Aktion unabhaengig davon, woher
  die Session kam.

**Negativ (bewusst akzeptiert)**

- Fuer Sessions mit gesetztem Haken ist die XSS-Angriffsflaeche fuer die Dauer
  von bis zu `sessionMaxAgeHours` tatsaechlich groesser als beim ADR-0035-
  Default — das ist der Preis der Reibungsreduktion, kein Seiteneffekt.
- Die Obergrenze ist eine CLIENT-seitige Durchsetzung (Vergleich im
  `SessionProvider` beim Boot). Sie ist damit gegen zwei Faelle wirkungslos:
  ein Angreifer mit Schreibzugriff auf `localStorage` (bereits erfolgreicher
  XSS) kann den Zeitstempel neu setzen, und ein aus dem Browser getragenes
  Token-Paar wird ausserhalb dieses Clients ueberhaupt nie geprueft — dort
  gilt allein die GoTrue-Token-Lebensdauer. Das aendert nichts an der
  grundsaetzlichen Einordnung: ein erfolgreicher XSS ist bereits das
  akzeptierte Rest-Risiko aus ADR-0035, diese ADR vergroessert dessen
  Wirkfenster nur fuer opt-in-Sessions, nicht dessen grundsaetzliche Existenz.
  Wer eine Grenze braucht, die auch gegen diese beiden Faelle traegt, braucht
  serverseitige Session-Verwaltung (Auth-BFF, s. Trigger fuer Re-Visit) —
  dieses Paket liefert sie ausdruecklich nicht.
- Der Cross-Tab-Logout ueber `BroadcastChannel` erreicht nur gleichzeitig
  offene Tabs (s. o., Entscheidung Punkt 5) — kein vollstaendiger Ersatz fuer
  eine serverseitige Session-Revocation-Liste.
- **Trigger fuer Re-Visit bleibt unveraendert von ADR-0035:** sobald ein
  Auth-BFF mit `httpOnly`-Cookies entsteht, ist das der Zielzustand fuer
  BEIDE Betriebsarten (Tab-Lifetime UND "angemeldet bleiben") — dann ersetzt
  eine weitere ADR sowohl ADR-0035 als auch diese.

## Verworfene Alternativen

- **`localStorage` fuer alle Sessions (kein Opt-in).** Verbessert die Reibung
  fuer alle, vergroessert aber die XSS-Flaeche fuer alle, auch fuer Nutzer,
  die das nie brauchen. Widerspricht dem Ziel, die Sperre nur fuer die
  Nutzer zu lockern, die das aktiv wollen.
- **`BroadcastChannel`-only ohne Storage-Wechsel** (Session bleibt in
  `sessionStorage`, nur ein Cross-Tab-Sync-Mechanismus). Loest nicht das
  eigentliche Problem — ein NEUER Tab (oder Browser-Neustart) haette
  weiterhin keine Session, weil `sessionStorage` grundsaetzlich nicht
  zwischen Tabs geteilt wird.
- **Cookie-Session (`httpOnly`) fuer diesen Anlass.** Verlangt einen
  Auth-BFF (server-seitiger Token-Tausch), den es laut ADR-0035 nicht gibt —
  das waere ein Umbau von ADR-0006, kein Fix fuer dieses Issue. Bleibt der
  langfristige Zielzustand (s. Trigger fuer Re-Visit), nicht die kurzfristige
  Antwort.
- **Zwei `createClient`-Instanzen (bzw. Neuaufbau beim Umschalten).**
  `createClient` bindet den Storage einmalig auf Modulebene
  (`lib/supabase.ts`) — ein zweiter Client waere eine zweite Quelle fuer
  denselben Zustand (Session-Drift zwischen beiden Instanzen). Der
  delegierende Adapter (EIN Client, Storage-Wahl pro Zugriff) vermeidet das.
- **Keine absolute Obergrenze (Session laeuft, solange sie benutzt wird).**
  Das waere ADR-0035s explizit verworfene Alternative B ohne Einschraenkung —
  genau das Ergebnis, das die XSS-Abwaegung unehrlich gemacht haette.

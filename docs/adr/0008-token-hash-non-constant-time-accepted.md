# ADR-0008 — API-Token-Hash-Vergleich bleibt nicht-konstantzeit (accepted)

- Status: Akzeptiert
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), MS-3 H3 Folge / Plan-Review 2026-05-26
- Bezug: F-04 in `docs/security-findings.md`

## Kontext

`PgTokenRepository.find_by_hash` macht `WHERE token_hash = $1`; ein
nachgelagertes `touch_last_used` schreibt nur bei Treffer. Hit und Miss
haben damit unterschiedliche Latenz — ein theoretischer Timing-Side-
Channel.

Der Channel leakt im schlimmsten Fall die *Existenz eines bestimmten
SHA-256-Hashes*. Klartext-Tokens sind 256 Bit Entropie aus
`secrets.token_urlsafe(32)`; ein Praeimage-Angriff auf SHA-256 ist
praktisch ausgeschlossen, ein Online-Bruteforce-Test ueber HTTP gegen
slowapi-Rate-Limits (30/min) ist auch theoretisch unrealistisch.

## Optionen

- **A — Status quo (DB-Lookup auf Hash-Spalte).** Schnell, F-04 bleibt
  offen.
- **B — Public-Prefix-Index + `hmac.compare_digest`.** Erste 8-12 Zeichen
  des Tokens werden im Klartext indexed; der Vergleich des Restes laeuft
  in `hmac.compare_digest`. Aufwand: Migration (neue Spalte + Index),
  Token-Format-Aenderung, Backfill alter Tokens (oder Forced-Rotation).
- **C — HMAC-mit-Server-Key statt SHA-256.** Aehnlicher Aufwand wie B,
  plus zusaetzliches Server-Key-Secret zu rotieren.

## Entscheidung

**A — Akzeptiert.** Der erwartete Schaden eines erfolgreichen Timing-
Angriffs (Hash-Existenz, ohne Klartext, ohne Owner-Bezug) rechtfertigt
weder die Migration (B) noch ein zusaetzliches Key-Material (C) zum
heutigen MVP-Zeitpunkt.

## Re-Evaluation-Trigger

Diese Entscheidung ist neu zu pruefen, sobald **eine** der folgenden
Bedingungen eintritt:

1. **Multi-User-Hosting:** Mehr als ein User-Owner pro Instanz
   (heute Single-Owner).
2. **Token-Auth-Last:** Anhaltend > 1 Request/Sekunde mit
   API-Token-Auth pro Owner ueber 7 Tage — Prometheus-Counter
   `who2be_auth_token_attempts_total` macht das messbar (ADR-0010).
3. **Public-Internet-Exposure ohne Caddy-Frontend:** Wenn die API je
   ohne `slowapi` davorgeschaltet erreichbar gemacht wird.

Bei Trigger: Option B (Public-Prefix-Index + `compare_digest`) umsetzen,
ADR-0008 ablegen, neues ADR mit Migration-Plan.

## Konsequenzen

- F-04 bleibt in `docs/security-findings.md` mit Status "Accepted" und
  Verweis auf diese ADR.
- Re-Eval-Trigger sind messbar (Trigger 2 ueber Prometheus, Trigger 1/3
  durch Deployment-Entscheidung).
- Kein Code-Aufwand jetzt; klarer Pfad fuer spaeter.
</content>
</invoke>
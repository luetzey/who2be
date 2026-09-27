# Pro-Preis auf 9,99 EUR + Drift-Waechter + ungedeckte Feature-Codes

Karte: `t_764730e3` · Branch: `who2be/t_764730e3-pro-preis-auf-9-99-eur-setzen-owner-ents`
Basis: `origin/main` @ `12176907`

## Owner-Entscheidung (nicht zu hinterfragen)

> „Ich finde fuer den Start 9.99 Euro gut." (2026-09-25)

Pro kostet `9.99` EUR/Monat. Mollie-Decimal-String, Intervall `1 month` unveraendert.

## Eigener Grep-Nachtrag (Stand 2026-09-26, gegen `origin/main` 12176907)

Der Kartentext nannte Zeilennummern gegen einen aelteren `main`; sie haben sich
verschoben. Gemessene Fundstellen (`grep -rnE '29[.,]00|29 ?€|29 ?EUR|"2900"|2900\b'`):

| Datei | Zeile (ist) | Kartentext sagte | Befund |
|---|---|---|---|
| `packages/billing/src/who2be_billing/plans.py` | 108 | 77 | `price_eur="29.00"` — **fuehrende Quelle** |
| `packages/billing/src/who2be_billing/plans.py` | 52 | 34 | Docstring-Beispiel `"29.00"` |
| `apps/web/src/features/billing/components/BillingPanel.test.tsx` | 179 | 96 | erwartet `'29 €/Monat'` |
| `apps/web/src/features/billing/components/BillingPanel.tsx` | 41 | **nicht genannt** | `priceEur: 29` — die tatsaechliche Anzeige-Quelle |
| `docs/licensing/plans.md` | 29 | 25 | Tarifzeile |
| `docs/cloud-hosting-owner-guide.md` | 46, 258, 268, 290, 298, 320, 454, 550 | acht Stellen (andere Nummern) | acht Stellen, bestaetigt |

Nachtraege zur Vollstaendigkeitspruefung, die der Kartentext verlangt hat:

- `2900` / `29,00` / `"29"` als Preis: **keine** weitere Fundstelle (die zwei
  `uv.lock`-Treffer sind Hash-/Zeitstempel-Rauschen).
- i18n: `apps/web/src/i18n/locales/{de,en}.json` enthalten **keinen** Preis. Der
  Billing-Namespace lebt in `apps/web/src/features/billing/i18n.ts` und traegt
  nur das Format `'{{amount}} €/Monat'` — die Zahl kommt aus `BillingPanel.tsx`.
- Frontend-Anzeige: `BillingPanel.tsx:41` ist die echte Quelle, nicht der Test.
  **Im Kartentext fehlte sie** — ohne sie waere der Test gruen und die UI falsch.
- Historie bleibt: `CHANGELOG.md`, `changelog.d/`, `docs/adr/`, `.claude/plan/`.

## `docs/cloud-hosting-owner-guide.md` — Kollisionsregel

Datei existiert noch (29158 Bytes). Also: **nur Preiszahlen**, keine
Umformulierung, keine andere Datei aus `t_2ef0060d` anfassen. Zwei Stellen sind
Rechnungen mit dem Preis als Faktor (Z. 454: `50 Kunden × 29 € ≈ 46 €/Monat`) —
dort wird die **abgeleitete Zahl mitgezogen**, weil sie sonst falsch waere; die
Formulierung bleibt Wort fuer Wort.

## Schritte

1. `plans.py`: `price_eur="9.99"`, Docstring-Beispiel ebenso. Intervall/Mollie-Syntax unangetastet.
2. `BillingPanel.tsx:41`: `priceEur: 9.99`. Pruefen, dass `perMonth` das Format nicht verstuemmelt.
3. `BillingPanel.test.tsx:179`: erwartet `'9,99 €/Monat'` bzw. den tatsaechlich gerenderten Wert (i18next-Formatierung pruefen, nicht raten).
4. `docs/licensing/plans.md:29`: Preis `9,99 €/Monat`; **Feature-Spalte auf `core`** reduzieren (drei ungedeckte Codes raus). §„Zur Features-Spalte" bleibt inhaltlich stehen, wird nur an den Wegfall angepasst, ohne die Aussage zu drehen.
5. `docs/cloud-hosting-owner-guide.md`: acht Preiszahlen + die eine abgeleitete Rechnung.
6. **Waechter** `packages/billing/tests/test_doc_price_drift.py`:
   - A (Anker): Tarifzeile in `docs/licensing/plans.md` nennt exakt `PRO_PLAN.price_eur`.
   - B (Anker): `BillingPanel.tsx` `priceEur` fuer `pro` == `PRO_PLAN.price_eur`.
   - C (Scan): alle `<betrag> €/Mon…`-Vorkommen in Doku + Billing-Code gegen eine
     Allowlist bekannter Betraege (Free 0, Pro = `plans.py`, Team-**Vorschlag** 99
     aus dem Analysepapier). Neue Fundstelle mit fremder Zahl = rot.
   - Jeder Anker prueft zuerst, dass sein Muster ueberhaupt noch trifft — ein
     stumm durchlaufender Guard ist schlimmer als keiner (Muster von `test_doc_tool_count.py`).
   - **Rot-Probe nachweisen:** Preis probeweise verstellen, Test bricht, zurueckdrehen.
7. Changelog-Fragment `changelog.d/pro-preis-999.changed.md`.
8. DoD-Kommandos aus `CONTRIBUTING.md`.

## Out of Scope (aus der Karte)

Free-Limits, dritter Tarif, Mollie-Konfiguration, Website-Texte.

## Oeffentlichkeits-Regel

Commit nennt die Entscheidung, keine Marge/Kalkulation/Kundenzahl-Annahme.

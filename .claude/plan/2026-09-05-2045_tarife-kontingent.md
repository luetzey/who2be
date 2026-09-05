# Tarife bewerben das Kontingent statt Feature-Codes (WP-2 von #428, Issue #449)

- Status: **in Arbeit**
- Datum: 2026-09-05, 20:45 UTC (23. Lauf)
- Issue: #449 (`agent-ready`, `size/S`), Eltern-Issue #428
- Branch: `claude/autonomous-code-agent-role-u3thhe`

## 1. Ask-Once-Gate

**Bestanden.** Outcome, sechs prüfbare Kriterien, Out-of-Scope, Verifikations-
Kommandos und fünf vorentschiedene Weichen stehen im Body.

## 2. Recherche: was der Client tatsächlich bekommt

`EntitlementInfo` (`apps/web/src/api/types.ts:980-988`) trägt:
`edition`, `status`, `features[]`, `expires_at`, `mcp_monthly_quota`,
`mcp_rate_per_min`, `usage`.

**Es gibt keinen `plan_code` im Response.** Weiche 3 nennt „`mcp_monthly_quota`
bzw. den Plan-Code" — verfügbar ist nur die erste Hälfte. `META_PLAN_CODE`
(`packages/billing/src/who2be_billing/plans.py:26`) existiert ausschließlich in
den Mollie-Metadaten, nicht am Entitlement.

Ebenso fehlen im Response die beiden **statischen Produktdaten**, die AC 1/AC 2
verlangen:

| Größe | Wert Free | Wert Pro | Quelle |
|---|---|---|---|
| Preis | 0,00 € | 29,00 €/Monat | `plans.py:66, 77` (`price_eur`) |
| MCP/Monat | 1.000 | 100.000 | Entitlement-Response ✔ |
| MCP/min | 30 | 240 | Entitlement-Response ✔ |
| Entity-Limit | 50 | unbegrenzt | `licensing/entitlement.py:52, 92-107` |

**Kein Blocker:** die Eskalationsklausel greift auf „eine Backend-Angabe für
*ist Pro*" — dafür genügt `mcp_monthly_quota`, und die kommt an. Preis und
Entity-Limit sind unveränderliche Produktdaten, keine Laufzeitwerte.

## 3. Befund: die Feature-Codes sind nicht wirkungslos

AC 1 erlaubt, die Feature-Spalte mit dem Vermerk zu versehen, die Codes seien
„technische Metadaten des Entitlements und kein Leistungsversprechen". **So
stimmt das nicht.** `Entitlement.entity_limit()` leitet genau aus ihnen ab:

```python
# apps/api/src/who2be_api/licensing/entitlement.py:105-107
paid_features = self.features - {Feature.CORE}
return None if paid_features else FREE_ENTITY_QUOTA
```

Wirksam ist also, **ob überhaupt ein Paid-Code vorliegt** — das hebt das
Entity-Limit von 50 auf unbegrenzt. Nicht wirksam ist die einzelne Zusage
hinter `composite_playbooks`, `agents` oder `audit_export`: kein `has_feature()`
gatet sie, und für `audit_export` existiert nicht einmal ein Endpunkt.

Die Doku muss diese Unterscheidung treffen, sonst ersetzt sie eine falsche
Aussage durch eine zweite. Formulierung: die Codes sind Metadaten, ihre
*Anwesenheit* hebt das Entity-Limit, die *einzelnen* Codes werden nicht gegatet.

## 4. Muster-Entscheidung

**Gewählt: Tarif-Tabelle als Datensatz-Liste** (`TIERS`-Konstante im
Billing-Feature) — je Tarif Code, Anzeigename, Preis, MCP/Monat, MCP/min,
Entity-Limit. Das Panel rendert daraus und erkennt den aktiven Tarif durch
Abgleich von `mcp_monthly_quota` gegen die Liste.

**Kompaktere Alternative, gegen die entschieden wurde:** zwei fest verdrahtete
Zweige (`if isPro … else …`) mit Literalen im JSX — kürzer, aber genau der
heutige Zustand in neuer Verkleidung.

**Beleg für Variabilität (Schwelle „bereits existierender zweiter Fall"):** es
gibt heute zwei Tarife (`FREE_PLAN`, `PRO_PLAN`, `plans.py:64, 75`), und
`PAID_PLANS` ist bereits als Dict über Codes angelegt (`plans.py:92`) — die
Mehrzahl ist im Backend also schon Struktur, nicht Sonderfall. Das Issue nennt
den dritten Tarif ausdrücklich als Ziel der Vorbereitung (AC 3).

**Risiko, benannt:** die Liste dupliziert Preis und Entity-Limit aus dem
Backend. Sie trägt deshalb einen Kommentar mit der Fundstelle (`plans.py`,
`entitlement.py`), damit eine Preisänderung nicht still auseinanderläuft. Ein
Backend-Feld dafür wäre sauberer, ist aber ein API-Paket und hier Out-of-Scope.

## 5. Arbeitspaket

1. `docs/licensing/plans.md`: Tabelle auf Preis / MCP-Monat / MCP-min /
   Entity-Limit; Feature-Spalte mit dem präzisen Vermerk aus §3.
2. `BillingPanel.tsx`: `PRO_FEATURES` raus, `TIERS`-Liste rein, `isPro` über
   `mcp_monthly_quota`; die vier Größen für den aktiven Tarif anzeigen.
3. `i18n.ts`: neue Strings DE/EN, identisches Keyset.
4. `BillingPanel.test.tsx`: die drei ungedeckten Zweige (`notFound`,
   Ladefehler, Checkout-Fehler) plus Tarif-Erkennung.
5. `CHANGELOG.md` + `.claude/context/STATE.md` als letzter Commit.

## 6. Verifikation

```bash
cd apps/web
npm run lint && npx tsc -b && npm run test:coverage && npm run build
npm test -- src/features/billing/components/BillingPanel.test.tsx
grep -rn "composite_playbooks\|audit_export" src/features/billing/
```

Baseline vor der Änderung (gemessen): Statements 86,52 · Branches 81,12 ·
Functions 82,05 · Lines 87,55 (Floors 80/79/75/80).

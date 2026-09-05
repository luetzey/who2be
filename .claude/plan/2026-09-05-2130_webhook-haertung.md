# Generischen Billing-Webhook härten (WP-5 von #428, Issue #452)

- Status: **in Arbeit**
- Datum: 2026-09-05, 21:30 UTC (24. Lauf)
- Issue: #452 (`agent-ready`, `size/S`), Eltern #428
- Branch: `claude/autonomous-code-agent-role-u3thhe`

## 1. Ask-Once-Gate

**Bestanden.** Outcome, sechs prüfbare Kriterien, Out-of-Scope, Verifikations-
Kommandos und sechs vorentschiedene Weichen stehen im Body.

**Einordnung des Befunds, unverändert übernommen:** heute **nicht ausnutzbar**.
Kein Anbieter sendet auf diesen Pfad (das Repo hängt allein an
`mollie-api-python`, und Mollie signiert nicht), und ohne gesetztes
`billing_webhook_secret` antwortet der Endpunkt auf jede Anfrage mit 400. Die
Härtung ist Vorsorge für den Tag, an dem ein signierender Anbieter dazukommt.

## 2. Zwei Stellen, an denen das Issue nicht durchentschieden ist

### 2.1 AC 4 — Zeitfenster im generischen Format

Der Stripe-Zweig prüft das Fenster gegen den Zeitstempel **aus dem Header**
(`webhook.py:68-72`). Das generische Format kennt keinen:

```python
# webhook.py:77-82 — nur sha256= plus Hex-Digest, kein Zeitbezug
candidate = header.strip()
if candidate.startswith("sha256="): candidate = candidate[7:]
expected = hmac.new(secret_bytes, payload, hashlib.sha256).hexdigest()
```

Ein Toleranzfenster braucht also eine Zeitquelle, die es dort nicht gibt.
**Leitplanke:** die Zeit aus dem *Event-Payload* ziehen (das `created`-Feld der
Stripe-Konvention, das `parse_event` ohnehin liest), nicht das Header-Format
erweitern — ein erweitertes Header-Format wäre ein Vertrag mit einem Anbieter,
den es nicht gibt. Fehlt die Zeitangabe im Payload, gilt **fail closed**:
abweisen, nicht durchlassen.

Trägt das nicht, ist es zu melden statt zu erfinden.

### 2.2 AC 5 — Monotonie ohne Migration

`entitlement_repository.py:88-102` schreibt `updated_at = now()`. Die Spalte
existiert also, **aber sie ist die Schreibzeit, nicht die Ereigniszeit des
Anbieters.** Ein Vergleich „Ereigniszeit < gespeichertes `updated_at`" ist damit
nur eine Näherung und kann ein legitimes, spät zugestelltes Ereignis abweisen —
genau der Fall, den die Eskalationsklausel des Issues nennt.

**Leitplanke:** Monotonie nur bauen, wenn sie ohne Migration **und** ohne
Abweisung legitimer Reihenfolgen funktioniert. Andernfalls: nach Weiche 4
schneiden (Reihenfolge absteigender Wirkung ist Ablauffrist → Dedupe →
Zeitfenster → Monotonie → Mount) und den Rest als Folge-Issue melden. Weiche 6
sagt ausdrücklich, dass eine Migration hier Aufwand und Risiko ohne Not wäre.

## 3. Muster-Entscheidung

**Keine neue Abstraktion.** Der Mollie-Pfad (`mollie.py:482, 500, 507-514`) ist
die Vorlage für Dedupe-Claim und Freigabe-bei-Fehler; der generische Pfad
übernimmt dasselbe Muster mit demselben `ProcessedEventRepository`. Eine
gemeinsame Basisklasse für „Webhook-Pfad" wäre die dritte Struktur für zwei
Fälle und ist nicht belegt — die Wiederverwendung läuft über das vorhandene
Repository, nicht über eine neue Hierarchie.

## 4. Reihenfolge (aus Weiche 4, absteigende Wirkung)

1. **Ablauffrist** — die wichtigste: sie allein macht jede Wiedereinspielung
   selbstlimitierend.
2. **Dedupe** über die Umschlag-Ereignis-Kennung, mit Freigabe bei Fehler.
3. **Zeitfenster** (siehe 2.1).
4. **Monotonie** (siehe 2.2) — schneidbar.
5. **Mount nur mit Secret** (404 statt 400).

## 5. Verifikation

```bash
uv run pytest packages/billing/tests -v
uv run ruff check . && uv run ruff format --check .
uv run mypy .
grep -n 'claim' packages/billing/src/who2be_billing/router.py
```

Baseline: 59 Billing-Tests grün. `--cov-fail-under=85` ist ohne Docker/DB in
dieser Session nicht erreichbar (gemessen 63,08 %, 448 Skips) — das prüft die
CI, im PR wird es offengelegt statt abgehakt.

Zusätzlich: **`security-reviewer`** über den Diff, weil CLAUDE.md das für
externe Inputs verlangt.

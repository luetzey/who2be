# Rechnung R2d — Schalter in Compose/.env.example + Doku

Kanban-Karte t_60600cd1 (Rechnung Mollie R2d). Grundlage ADR-0061 §5, §7, §8, §9, §13.

## Ziel

`WHO2BE_INVOICE_TAX_MODE` und `WHO2BE_INVOICE_PRICE_BASIS` erreichen in allen
drei Cloud-Overlays die Container, die sie lesen, mit sicherem Default. Die
Betreiber-Doku beschreibt Rechnung, Archiv, Storno und Löschung nach ADR-0061.

## Befund (gemessen gegen origin/main 2660d2c3)

- `Settings` liest beide Schalter (`core/config.py`), Default Steuermodus leer
  (fail closed), Preisbasis `net`. Kein Overlay reicht sie durch.
- Gelesen werden sie an zwei Stellen: im `api` (Checkout-Betrag, R2c, ohne
  Steuermodus 503) und im `worker` (Routine `invoice-retry`, R2b).
- Der `worker` bekommt in keinem Cloud-Overlay `MOLLIE_API_KEY`. Die Routine
  `invoice-retry` bricht dann mit `MOLLIE_API_KEY fehlt` ab
  (`who2be_billing/invoice.py#run_invoice_retry`): ohne die Zeile entsteht in
  Produktion nie eine Rechnung. Gehört zum Durchreichen dazu.
- Doku: GoBD §1/§4/§5/§6 beschreiben noch „keine eigenen Rechnungen“;
  `cloud-erstinbetriebnahme` nennt den 503 ohne Steuermodus nicht und hat
  keinen Storno-Ablauf; VVT und Löschkonzept kennen `billing_invoice` nicht.

## Schritte

1. Compose: `api` + `worker` je Overlay (Root, Hetzner, Dokploy) —
   `WHO2BE_INVOICE_TAX_MODE: ${…:-}`, `WHO2BE_INVOICE_PRICE_BASIS: ${…:-net}`,
   im `worker` zusätzlich `MOLLIE_API_KEY: ${…:-}`. Dokploy-Kopf nennt beide.
2. `.env.example` (Root): auskommentierte Einträge mit Erklärung, ohne Empfehlung.
3. GoBD-Verfahrensdokumentation §1, §4, §5 (neu gefasst), §6 (Stand nachgezogen).
4. `cloud-erstinbetriebnahme.md`: Schalter für den Testlauf, Storno-Ablauf,
   Fehlerbild 503/Rechnung bleibt aus.
5. VVT §3 (Rechnungen), §5 (Mollie-Empfänger), §7 (Frist).
6. Löschkonzept §3 (Rechnungsarchiv), §6 (Übersicht).
7. Changelog-Fragment.

## Verifikation

- `uv run pytest apps/api/tests/test_cloud_compose_billing_override.py
  apps/api/tests/test_compose_env_promises.py apps/api/tests/test_compose_hardening.py
  apps/api/tests/test_single_writer_guard.py apps/api/tests/test_dependabot_compose_coverage.py`
- YAML-Prüfung aller drei Overlays (Scratch-Skript): beide Schalter in `api`
  und `worker`, Steuermodus `${…:-}`, Preisbasis `${…:-net}`, `MOLLIE_API_KEY`
  im `worker`. Mutationen dagegen im Scratch.
- Öffentlichkeitsregel: keine Werte mit Steuerbezug als Empfehlung, keine
  Preise/Kosten, keine echten Adressen/USt-IdNr./Keys.

## Datei-Deckel (≤ 8, Changelog und Plan zählen nicht)

3 Compose + `.env.example` + 4 Doku = 8. Nicht enthalten, weil über dem
Deckel: ein Regressionstest im Repo für die Durchreichung und
`deploy/hetzner/.env.example`. Beides als Frage an den PM (needs_input).

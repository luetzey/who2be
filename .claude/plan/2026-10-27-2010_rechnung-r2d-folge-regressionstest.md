# Rechnung R2d-Folge — Regressionstest Rechnungs-Schalter + Hetzner-.env.example

Kanban-Karte t_025a84b5 (Folge aus dem Review von #1087). Grundlage ADR-0061 §5.
Abgezweigt von origin/main 7ef15b8a (#1087 gemergt).

## Ziel

Die Verdrahtung aus #1087 ist durch einen Test im Repo gesichert, und die
Betreiber-Vorlage `deploy/hetzner/.env.example` nennt beide Schalter.

## Schritte

1. `apps/api/tests/test_cloud_compose_invoice_switches.py` (Muster
   `test_cloud_compose_billing_override.py`), je Overlay (Root, Hetzner, Dokploy):
   - `WHO2BE_INVOICE_TAX_MODE` in `api` und `worker`, genau `${…:-}` (kein Default),
   - `WHO2BE_INVOICE_PRICE_BASIS` in `api` und `worker`, genau `${…:-net}`,
   - `MOLLIE_API_KEY` im `worker`,
   - Werte an `api` und `worker` identisch,
   - der aufgeloeste Compose-Default ergibt in `Settings` fail closed
     (Steuermodus `None`, Preisbasis `net`) — Verhaltens-Teil des Tests.
   - Hetzner-`.env.example` nennt beide Schalter auskommentiert, Steuermodus ohne Wert.
2. `deploy/hetzner/.env.example`: auskommentierte Eintraege mit Erklaerung,
   ohne Wertempfehlung (Wortlaut wie Root-`.env.example`).
3. `docs/cloud-erstinbetriebnahme.md` Schritt 6: Hinweis, den Steuermodus schon
   hier einzutragen (Review-Nit N1), Verweis auf Schritt 15.
4. `changelog.d/rechnung-r2d-folge-regressionstest.changed.md`.

## Verifikation

- Gegenprobe: Test rot bei entfernter Zeile / Default am Steuermodus / Preisbasis-Default
  `gross` / fehlendem `MOLLIE_API_KEY` am worker (temporaer, nicht committet).
- DoD aus CONTRIBUTING.md (ruff, format, mypy, pytest mit Coverage-Gate, check_code_refs).

## Ergebnis

(wird nachgetragen)

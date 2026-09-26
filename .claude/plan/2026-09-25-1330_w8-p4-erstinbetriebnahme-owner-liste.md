# W8/P4 — Erstinbetriebnahme-Anleitung fuer den Owner

**Karte:** `t_d9146f62` · **Branch:** `who2be/t_d9146f62-w8-p4-erstinbetriebnahme-anleitung-fuer`
**Gemessen gegen:** `origin/main` @ `cee6478e` (Stand Rebase dieses Branches)

## Ziel

Eine abhakbare Vorbereitungsliste, die der Owner vom Handy aus abarbeiten kann,
nach **Vorlaufzeit** sortiert — nicht nach Wichtigkeit. Je Schritt: wer, wie
lange, was danach anders ist.

## Entscheidung: neues Dokument, kein vierter Konkurrent

`docs/cloud-erstinbetriebnahme.md` **neu**, nicht als RUNBOOK-Abschnitt.
Begruendung:

- Der RUNBOOK hat 1247 Zeilen und ist laut eigenem Kopf die Quelle fuer
  *Incident-Response, CVE-Triage, Secret-Rotation*. Die Owner-Vorbereitung
  (Konten besorgen, OAuth-Apps anlegen, SMTP-Weiche) ist keine Operator-
  Prozedur auf einer laufenden Box — sie passiert **davor** und teils ganz
  ausserhalb des Servers. Sie dort einzuhaengen hiesse: der Owner scrollt
  unterwegs durch ein Wartungshandbuch.
- Die Nicht-Konkurrenz wird strukturell hergestellt, nicht versprochen: das
  neue Dokument **duplizert keine Prozedur**. Provisioning-Kommandos bleiben im
  RUNBOOK, Bring-up im `deploy/hetzner/README.md`, die Abnahme-Reise in
  `docs/cloud-prod-smoke.md`. Das neue Dokument traegt genau das, was heute
  **nirgends** steht: Beschaffungs-Vorlauf, OAuth-Zugangsdaten mit exakter
  Redirect-URI, die SMTP-Weiche als Entscheidung, und die Reihenfolge.
- Gegenprobe gegen Drift: RUNBOOK-Checkliste und `deploy/hetzner/README.md`
  bekommen je einen Zeiger nach vorn; `docs/README.md` den Index-Eintrag.

## Schritte

1. Repo-Verifikation aller Angaben (erledigt, Belege s. u.).
2. `docs/cloud-erstinbetriebnahme.md` schreiben.
3. Zeiger setzen: RUNBOOK §Erste Inbetriebnahme (Schritt 0), `deploy/hetzner/README.md`
   §Cloud-Edition, `docs/README.md` §How-To.
4. Changelog-Fragment `changelog.d/w8p4-erstinbetriebnahme.added.md`.
5. DoD: `check_code_refs.py`, `changelog_fragments.py guard`, ruff/mypy
   (keine Python-Aenderung, aber Gates laufen lassen).

## Was gegen das Repo verifiziert wurde (nicht aus dem Bericht uebernommen)

| Angabe | Beleg auf `main` |
|---|---|
| Redirect-URI `https://supabase.<DOMAIN>/auth/v1/callback` | Compose-Default `GOTRUE_EXTERNAL_{GOOGLE,GITHUB}_REDIRECT_URI` in `deploy/hetzner/supabase/docker-compose.yml` |
| DNS: `api.`/`app.`/`supabase.` Pflicht, `mcp.` optional | `deploy/hetzner/Caddyfile` (vier Site-Blocks), RUNBOOK §Provisioning Schritt 5 |
| At-Rest vor dem ersten `docker compose up` | RUNBOOK §Provisioning Schritt 1 + §Verschluesselung at-Rest |
| `JWT_SECRET` identisch in beiden `.env`, >= 32 Zeichen | beide `.env.example`, RUNBOOK Schritt 6 |
| `SEAWEEDFS_S3_SECRET_KEY` ist **hart** Pflicht (`:?`-Guard) | `deploy/hetzner/who2be/docker-compose.yml`, `seaweedfs`-Service |
| `gen_test_jwt.py --secret/--role/--ttl` | `scripts/gen_test_jwt.py#_parse_args` |
| Override: `admin` + `aal2` + Allowlist, API-Token kategorisch aus | `packages/billing/src/who2be_billing/router.py#create_override`, `#_require_override_operator`, `apps/api/src/who2be_api/core/security.py#require_aal2` |
| Allowlist erreicht den Container auf `main` **nicht** | `grep OVERRIDE deploy/hetzner/who2be/docker-compose.cloud.yml` → kein Treffer; Fix in offenem PR #636 |
| Free/Pro-Zahlen | `packages/billing/src/who2be_billing/plans.py`, `apps/api/src/who2be_api/licensing/entitlement.py` |
| GoTrue-Pin `v2.196.0` | `deploy/hetzner/supabase/docker-compose.yml` |
| Externe Identitaet mit verifizierter Provider-Mail wird **ohne** Mail bestaetigt | GoTrue v2.196.0, [`createAccountFromExternalIdentity`](https://github.com/supabase/auth/blob/v2.196.0/internal/api/external.go): `decision.CandidateEmail.Verified \|\| config.Mailer.Autoconfirm` ⇒ `user.Confirm(tx)`; sonst `sendConfirmation` + `provider_email_needs_verification`. `GOTRUE_MAILER_ALLOW_UNVERIFIED_EMAIL_SIGN_INS` ist im Repo **nirgends** gesetzt ⇒ Default `false` |
| Cloud braucht weiter SMTP fuer Einladungen/E-Mail-Wechsel | `apps/api/src/who2be_api/integrations/gotrue_mailer.py`; GoTrue prueft `External.Email` nicht in `/invite`, `/verify` |
| Auf `main` ist in der Cloud E-Mail/Passwort noch AN | `deploy/hetzner/supabase/docker-compose.yml`: `GOTRUE_EXTERNAL_EMAIL_ENABLED: "true"` hart; Umstellung in offenem PR #631 |

## Abweichung vom Quellbericht (`cloud-testlauf-readiness-2026-09-24.md`)

Der Bericht behandelt SMTP als Owner-Entscheidung mit zwei Auswegen. Die
Auth-Umstellung aendert das qualitativ: **fuer den Solo-Testlauf entfaellt die
SMTP-Frage ganz**, sobald #631 auf `main` ist und der Owner sich per
Google/GitHub mit verifizierter Provider-Mail anmeldet — GoTrue bestaetigt den
Account dann selbst. Das steht deshalb ganz oben im Dokument. Nicht entfaellt
SMTP fuer Team-Einladungen; die sind aber nicht Teil des Testlaufs.

Zweite Abweichung: der Bericht nennt zwei 403-Fallen. Auf `main` ist die erste
davon **haerter** als beschrieben — die Variable steht nicht nur in keiner
`.env.example`, sie ist in **keiner** `environment:`-Liste des Hetzner-Cloud-
Overlays; kein `.env`-Eintrag der Welt hilft, bis #636 gemergt ist.

## Out of Scope (Karte)

Code aendern, Konten anlegen, deployen, Smoke-Dokumente ersetzen.

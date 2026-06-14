# Public-Switch: `luetzey/who2be` privat → public

**Status:** Plan, noch nicht umgesetzt
**Datum:** 2026-05-27
**Branch:** `claude/charming-ramanujan-I2qlB`
**Abhaengigkeit:** Phase A aus `.claude/plan/2026-05-27-1935_license-fsl-setup.md`
muss VORHER gemerged sein (LICENSE.md, README-Sektion, CONTRIBUTING-Skelett).

## Outcome

Das GitHub-Repo `luetzey/who2be` ist oeffentlich, mit korrekter Lizenz, einer
Public-tauglichen Doku-Schicht und einem privaten Sandbox-Mechanismus fuer
Experimente. Code-Komfort fuer den Solo-Dev bleibt erhalten, die Adoption-/
Vertrauens-Vorteile von Public-from-day-one werden eingeloest.

## Entscheidungen (final)

- **Repo-Strategie:** Variante B aus dem Pre-Plan-Gespraech — `luetzey/who2be`
  oeffentlich (saubere Schicht), zusaetzlich ein Sandbox-Pfad fuer Experimente.
- **Lizenz:** FSL-1.1-Apache-2.0 (siehe Lizenz-Plan).
- **CLA:** Konfiguration vorbereiten, aktivieren erst **mit** Public-Switch
  (vor Public bringt der CLA-Bot nichts).
- **History-Rewrite:** **Nein.** `luetzey@gmail.com` in den 121 bestehenden
  Commits bleibt stehen (ist eh auf GitHub-Profil sichtbar). Anonymisierung
  greift nur fuer neue Commits, falls gewuenscht.
- **Sicherheits-Audit:** ist bereits in dieser Session durchgefuehrt — keine
  echten Secrets in Tree oder History (gitleaks + 8 zusaetzliche Pattern-Scans
  ueber gesamte History). Ergebnis dokumentiert in dieser Plan-`## Notes`.

## Sicherheits-Audit-Ergebnis (vorgezogen, 2026-05-27 1935)

✅ **Sauber:**
- Keine `.env`-Datei jemals in der History (nur `.env.example`-Templates mit
  `CHANGE_ME` / Dev-Defaults).
- Keine echten JWTs, Private Keys, AWS-/GitHub-/Anthropic-/OpenAI-/Stripe-/
  Slack-/Google-API-Keys in 121 Commits.
- `.claude/settings.local.json` nie committed (durch `.gitignore` geschuetzt).
- Die 6 gitleaks-Treffer sind alle Test-Fixtures
  (`_TEST_SECRET = "integration-test-jwt-secret-padding-0123456789"`) und
  Local-Smoke-Doku-Beispiele.

⚠️ **Drei Sichtbarkeits-Punkte** (kein Security-Risiko, bewusste Entscheidung):
1. `docs/security-findings.md` listet 13 Findings (9 gefixt, 4 deferred).
2. `.claude/project.json` enthaelt Notion-IDs (kein Zugriff damit, aber
   Workspace-Existenz public).
3. Git-History enthaelt `luetzey@gmail.com` in 121 Commits (auch auf
   GitHub-Profil sichtbar).

## Schritte

### Phase 1 — Pre-Switch-Bereinigung (auf privatem Repo)

1. **`docs/security-findings.md` review.** Die vier deferred/akzeptierten
   Findings (F-04, F-11, F-12, F-13) durchgehen und pruefen, ob die
   Beschreibungen Exploitation-Details enthalten, die einem Angreifer einen
   Hebel geben. Falls ja: auf "Risiko-Klassifikation + Mitigation-Plan"
   kuerzen, ohne Reproduce-Schritte.
2. **`.claude/project.json` Entscheidung.**
   - Option A (Vorzug): Datei in `.gitignore` aufnehmen, einen Template-
     Eintrag `.claude/project.example.json` committen, die echte Datei
     lokal halten.
   - Option B: Belassen — Notion-IDs sind ohne Workspace-Zugriff nutzlos.
   - Entscheidung im Plan markieren bevor umgesetzt.
3. **Optional: kuenftige Commit-Identitaet anonymisieren.**
   `git config user.email "56551649+luetzey@users.noreply.github.com"`
   — neue Commits nutzen dann die GitHub-Noreply-Adresse. Alte History
   bleibt unveraendert. Nur ausfuehren, wenn der User das explizit will.
4. **`docs/CLAUDE-PROFILE.md` und `CLAUDE.md` pruefen** auf Inhalte, die
   im Public-Repo nicht stehen sollten (Notion-Workspace-Interna,
   Persoenliches). Schnell-Scan, keine Tiefen-Edit erwartet.

### Phase 2 — Lizenz-Setup (verweist auf Lizenz-Plan)

5. **`LICENSE.md`, README-License-Sektion, CONTRIBUTING-Skelett** committen
   und mergen — siehe `2026-05-27-1935_license-fsl-setup.md` Phase A.
   Public-Switch ohne diese Dateien waere unprofessionell und unsicher.

### Phase 3 — Sandbox-Setup (vor Public-Switch)

6. **Sandbox-Variante waehlen** (offene Klaerung, siehe unten):
   - 3a: Lokaler Branch `sandbox/*` mit `push.default current` und
     ohne Remote-Tracking — kein zweites Repo, kein zweites CI.
   - 3b: Separates privates GitHub-Repo `luetzey/who2be-lab` — Code
     dort experimentieren, fertige Sachen via Cherry-Pick / PR ins
     Public-Repo.
7. **Sandbox-Konvention dokumentieren** in `CONTRIBUTING.md` oder einer
   eigenen `docs/dev-workflow.md` — kurz: was geht in den Sandbox, was
   in den oeffentlichen PR-Pfad.

### Phase 4 — Public-Switch

8. **GitHub-Repo-Settings:**
   - Description setzen: "Self-hosted AgentDB for versioned persona and
     playbook management."
   - Topics: `agents`, `mcp`, `persona`, `playbook`, `self-hosted`,
     `fastapi`, `react`, `vite`, `source-available`, `fsl`.
   - Visibility: Private → Public.
9. **Native Public-Features aktivieren:**
   - Issues: an.
   - Discussions: an (Q&A + Ideas — niedrige Reibung fuer Community-Feedback).
   - Security Advisories: an (fuer Embargo-Workflow bei CVE-wuerdigen Fixes).
   - Sponsors: optional, erst spaeter.
10. **CLA-Assistant** (<https://cla-assistant.io>) aktivieren — referenziert
    aus `CONTRIBUTING.md`. Blockiert PR-Merges bis CLA-Signatur.
11. **Branch-Protection** auf `main`: Required-Reviews=1, Status-Checks=CI
    muss gruen sein, kein Force-Push, Direct-Push verboten (auch fuer
    den Owner — schuetzt vor Versehen).
12. **`SECURITY.md`** im Repo-Root: Hinweis auf Private Security Advisories
    fuer Vulnerability-Reports, Disclosure-Policy (Standard 90 Tage).

### Phase 5 — Post-Switch (deferred, eigene Tasks)

- Erste oeffentliche Release-Tag-Strategie (`v0.1.0`?) — separater Plan.
- Marketing-Launch (HN, Reddit, etc.) — bewusste Entscheidung, nicht
  automatisch mit Public-Switch.
- Trademark-Anmeldung "Who2Be" — siehe Lizenz-Plan Phase C.

## Acceptance Criteria

- [ ] `docs/security-findings.md` ist public-tauglich review't.
- [ ] `.claude/project.json` Entscheidung getroffen und umgesetzt.
- [ ] LICENSE.md, README-Sektion, CONTRIBUTING-Skelett, `SECURITY.md`
      im Repo, alle Tests gruen, gemerged auf `main`.
- [ ] Sandbox-Variante gewaehlt und dokumentiert.
- [ ] GitHub-Repo `luetzey/who2be` ist auf "Public" gesetzt.
- [ ] Issues, Discussions, Security Advisories aktiviert.
- [ ] Branch-Protection auf `main` aktiv.
- [ ] CLA-Assistant aktiv und in CONTRIBUTING.md verlinkt.
- [ ] `git status` clean, Branch `claude/charming-ramanujan-I2qlB` gepusht.

## Offene Klaerung vor Umsetzung

1. **Sandbox-Variante 3a (lokaler Branch) oder 3b (separates Repo)?**
   Empfehlung: 3a starten — null Setup-Aufwand, kann jederzeit zu 3b
   aufgewertet werden, wenn lokaler Branch zu klein wird.
2. **Commit-Identitaet fuer neue Commits anonymisieren** (Schritt 3)
   — ja oder nein?
3. **`.claude/project.json` Option A (gitignoren) oder B (belassen)?**
   Empfehlung: A — kostet eine Zeile `.gitignore` und ein Template,
   schadet nicht.

## Out of Scope dieses Plans

- Trademark-Anmeldung.
- Erstes Release-Tagging / Versioning-Strategie.
- Marketing-Launch / Community-Building / Discord etc.
- IP-Assignment Privatperson → Firma (siehe Lizenz-Plan Phase C).
- Enterprise-SKU / Pricing-Seite publik machen.

## Notes / Aenderungen

2026-05-27 2028 — V1.0: Initial-Anlage. Sicherheits-Audit aus der
vorgelagerten Session-Phase eingearbeitet (alle gitleaks-Findings
False-Positives, keine Production-Secrets in History). Plan ist
abhaengig vom Lizenz-Plan und wird erst danach umgesetzt.

# Repo-Pflege: Status-Nachführung & Aufgaben-Abhaken (2026-08-20)

**Status: umgesetzt (dieser Branch)** · Playbook: Repo-Pflege (Doku & Struktur)
· Anlass: User-Auftrag „Doku pflegen, erledigte Aufgaben abhaken,
Zusammenfassung offener Aufgaben".

## Gap-Report (Inventar-Ergebnis)

**Negativ-Listen-Scan:** keine Funde (Tree sauber; History-Beleg gitleaks
2026-07-22, zuletzt bestätigt im Lauf 2026-08-20 / PR #389).

**Track DOKU:** Die Public-Artefakte (README, CHANGELOG, CONTRIBUTING,
SECURITY, SUPPORT, ROADMAP, Issue-Forms, docs-Index, OpenAPI-Referenz) sind
seit PR #389 (gemergt 2026-08-20) aktuell und englisch — kein Stale-Fund.
Stale ist ausschließlich das **interne Status-Tracking**:

| Fund | Beleg | Maßnahme |
|---|---|---|
| `.claude/plan/README.md` führt die drei letzten Läufe nicht | Zeilen enden bei `2026-08-19-1700`; es fehlen `2026-08-19-1805` (Refactoring Web-Dedup), `2026-08-19-2110` (Branch-Hygiene/E2E, PR #387), `2026-08-20-0813` (Doku & Struktur, PR #389) | 3 Status-Zeilen nachtragen |
| Issue #338 O1 unabgehakt, obwohl erledigt | CI-Gate läuft seit 2026-08-16 wieder (STATE.md §Standards / CI, Runs mit echten Runnern; erster Lauf fand real 2 ESLint-Errors) | Checkbox O1 auf `[x]` setzen + Erledigt-Vermerk im Issue-Body |
| STATE.md §Repo-Pflege 2026-08-20 nennt PR #389 nicht als gemergt | Merge-Commit `5706fcb` auf `main` | Ein-Zeilen-Nachtrag (PR #389 gemergt) + dieser Lauf ergänzt |

**Track STRUKTUR:** keine neuen Funde. Community-Health bleibt begründet auf
Stufe 2 (Entscheidung aus dem Lauf 2026-08-20). Offene Struktur-Punkte sind
sämtlich Owner-gebunden (Description/Topics, Branch-Protection,
Auto-delete, Discussions, Social-Preview) und in #338/#388 getrackt.

**Bewusst NICHT in diesem Lauf** (Abgrenzung Playbook): #385 ist ein
Code-Fix (Test-Skip-Guard), kein Doku-Fund — bleibt offen im Backlog;
#388/#338 O2–O4 sind Owner-Schritte.

## Abhak-Prüfung der offenen Issues (Belege)

- **#338 O1** ✅ — CI-Gate aktiv seit 2026-08-16 (s. o.). O2–O4 offen (Owner).
- **#341 WP-8** offen — Root-`pyproject.toml` trägt weiterhin `version = "0"`,
  kein Tag. **WP-9** teilerledigt: die vier E2E-Journeys sind scharf
  (`journeys.spec.ts` ohne `fixme`, PR #387), aber `continue-on-error: true`
  steht noch in `ci.yml` (Z. 171) und der CI-Grün-Nachweis auf einem
  Release-Commit fehlt → Checkbox bleibt offen. **WP-10** offen.
- **#385** offen (Code-Fix, s. Abgrenzung). **#388** offen (Owner-Schritt).

## Arbeitspakete (kleiner Lauf, keine Aufteilung)

1. `.claude/plan/README.md`: 3 Status-Zeilen nachtragen.
2. `.claude/context/STATE.md`: PR-#389-Merge + diesen Lauf vermerken.
3. GitHub #338: O1 abhaken (Body-Update) + kurzer Beleg-Kommentar.
4. PR (draft) mit Pointer auf diese Plan-Datei; Zusammenfassung der
   offenen Aufgaben als Antwort an den User.

Kein CHANGELOG-Eintrag: reine interne Status-Pflege ohne Außenwirkung.

## Offene Aufgaben (Zusammenfassung, Stand 2026-08-20)

**Vorhaben „Public-Switch & erstes Release (v0.1.0)"** (`.github/PROJECT.md`):

*Owner-Schritte (nicht aus der Session setzbar):*
- #338 O2: Repo-Settings — Branch-Protection `main`, Auto-delete head
  branches, Merge-Strategie, Description + Topics (Textvorschläge in PR #389).
- #338 O3: CLA-Assistant aktivieren + Link in CONTRIBUTING.
- #338 O4: Visibility-Flip Private → Public (nach grünem CI-Lauf).
- #388: 70 tote Remote-Branches löschen (Kommandos liegen im Issue);
  Restliste `…-setup-4fk7ed` sichten.
- Owner-Entscheidungen aus `docs/standards-review-2026-07-20.md` §4
  (ADR-0002 enforce vs. amend, On-Prem-RLS, coverage.all/E2E-Hard-Gate, …).
- README: Screenshot/GIF als visueller Anker; Social-Preview-Bild;
  ggf. Discussions.

*Codebare Aufgaben:*
- #341 WP-8: Version `0` → `0.1.0`, Tag + GitHub-Release mit Notes.
- #341 WP-9 (Rest): grüner CI-Lauf auf Release-Commit, dann
  `continue-on-error` im e2e-Job entfernen (Owner-Soft-Gate-Entscheidung).
- #341 WP-10: Deploy-Pipeline einmal end-to-end (`DEPLOY_HOST`) — Pflicht
  erst vor 1.0.
- #385: Skip-Guard für `test_resource_slug_children_duplicate.py`.
- Dependabot: #384 (Ruff-Bump + Reformat in einem Schritt), #330/#240
  (Actions-Bumps, CI läuft jetzt — verifizierbar).
- PR #314 (Pitch-Dossier, Draft): Owner-Entscheidung mergen/schließen.

*Backlog (nach Release, ROADMAP/STATE):*
- WorkArea P1: KB-TTL-Verfall, Challenger-/Gegenbeleg, Drift-Erkennung.
- WorkArea P2: Kanten-Graph-UI, semantische Suche auf `wa_chunk`.
- ADR-0046: Schwellen-Kalibrierung gegen reales Embedding-Modell.
- Manuelle Compose-Verifikation Blobstore (braucht Docker-Umgebung).
- Folgelauf Refactoring: Personas-/Playbooks-Inline-Transition-Logik,
  Python-Service-Duplikate (DB-gebundenes Sicherheitsnetz nötig).
- Info-Befund I-1: Export-Volumen im Zugriffslog untererfasst.
- UX-Backlog `2026-06-27-1200` (Draft-Discard, Schnellfreigabe); OAuth
  Phase 2 (TTL-Cleanup, Audience-Trennung, aal2-Consent); E2E-Lauf mit
  echtem Claude/ChatGPT-Client.

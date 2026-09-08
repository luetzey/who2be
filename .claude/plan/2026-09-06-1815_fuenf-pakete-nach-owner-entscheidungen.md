# Fünf Pakete nach den Owner-Entscheidungen (2026-09-06, 18:15)

Umsetzungslauf über die gesamte startbare Warteschlange, nachdem der Owner am
2026-09-06 die drei offenen Weichen entschieden hat (#471 → B, #453 → C,
#462 → C). Damit sind **fünf** Pakete `agent-ready` statt zwei.

Auftrag: „Make everything you can" — alle fünf, in Wellen.

## Ausgangslage

- `main` = `9316e20` (Merge PR #476, ADR-0051/Fehlercodes), CI grün (Run 986).
- Arbeitsbranch `claude/autonomous-code-agent-role-s6x8z9`, identisch mit `main`.
- Warteschlange #442 trug #470 und #469; #471/#453/#462 sind heute dazugekommen.

## Pakete

| # | Inhalt | Stack | Größe |
|---|---|---|---|
| #470 | `WHO2BE_SESSION_MAX_AGE_HOURS` in beide `web`-Services durchreichen | Compose/Doku | trivial |
| #469 | `require_aal2` in `TokenService.create` + `.rotate` ab Rolle `admin` | Python | S |
| #471 | Storage-Entscheidung pro Tab einfrieren (Weg B) | Web | S |
| #453 | Billing-E2E-Journey + eigener Cloud-CI-Job (Weg C) | Web + CI | S |
| #462 | Monotonie-Auflage als Vermerk verankern (Weg C), kein Verhalten | Python/Doku | S |

## Muster-Benennung

**Keine Muster-Entscheidung nötig** — in keinem der fünf Pakete wird eine neue
Abstraktion eingezogen.

Der einzige strukturelle Eingriff ist #471, und er geht in die **Gegenrichtung**:
der delegierende Storage-Adapter (`lib/supabase.ts:32-49`) bleibt als Adapter
bestehen, nur seine Auflösungs-Strategie wechselt von „bei jedem Zugriff neu
lesen" auf „einmal pro Tab bestimmt". Das *entfernt* eine Indirektion, statt
eine hinzuzufügen — nach der Muster-Disziplin (Abschnitt „Gegenrichtung") ist
das der bevorzugte Weg. #469 verwendet mit `require_aal2` bewusst eine
bestehende Funktion wieder, statt ein zweites Gate zu bauen (Weiche 2 des
Issues); #462 fasst überhaupt keinen ausführbaren Code an.

## Wellen

Die fünf Pakete sind auf ihren **Produktivdateien** vollständig disjunkt. Nicht
disjunkt sind die Sammelpunkte (`CHANGELOG.md`, `.claude/context/STATE.md`,
`DECISIONS.md`) — und, weniger offensichtlich, die **Testläufe**: `pytest` und
`vitest` sehen den ganzen Arbeitsbaum, nicht nur die Dateien ihres Pakets. Zwei
gleichzeitig laufende Sub-Agents im selben Stack würden sich gegenseitig halb
geschriebene Dateien in den Testlauf ziehen und rote Läufe erzeugen, die keinem
Fehler entsprechen.

Daraus folgt die Wellen-Regel dieses Laufs: **pro Welle höchstens ein Paket je
Stack.**

- **Welle 1:** #469 (Python) ‖ #471 (Web) — dazu #470 (Compose, kein Stack-Test)
  vom Orchestrator selbst.
- **Welle 2:** #462 (Python) ‖ #453 (Web + CI).

**Sammelpunkte:** kein Sub-Agent fasst `CHANGELOG.md`, `STATE.md` oder
`DECISIONS.md` an. Diese Einträge schreibt der Orchestrator pro Paket beim
Commit — das ist die Doku-Ausnahme der Delegations-Regel und hält den
Ein-Zeilen-Merge klein.

## Modell-Right-Sizing

- **#470 — kein Sub-Agent.** Zwei Compose-Zeilen und zwei entfernte
  `.env.example`-Hinweise, ohne Design-Entscheidung. Das ist die ausdrückliche
  Ausnahme der Delegations-Regel; ein Sub-Agent kostete hier mehr, als er bringt.
- **#469 — Sonnet.** Klar umrissenes Paket mit entschiedener Weiche; die Arbeit
  ist ein Gate-Aufruf plus fünf Testfälle.
- **#471 — Sonnet.** Ebenfalls klar umrissen, aber verhaltenssensibel
  (Reihenfolge in `signOut`), deshalb nicht kleiner.
- **#453 — Sonnet.** Zwei Artefakte (Spec + CI-Job) mit acht vorentschiedenen
  Weichen.
- **#462 — Haiku.** Ausschließlich Kommentare und Doku, kein ausführbarer Code;
  die Verifikation ist ein `grep`, das leer sein muss.

## Verifikation je Paket

Aus den Issues übernommen, nicht erfunden:

- **#470:** `docker compose config` (Root + Hetzner mit `--env-file .env.example`),
  `scripts/smoke.sh`.
- **#469:** `uv run pytest apps/api/tests/test_token_service.py apps/api/tests/test_tokens.py apps/api/tests/test_mfa_aal2.py -v`,
  dann `--cov --cov-fail-under=85`, ruff/mypy.
- **#471:** `npm run lint`, `tsc -b`, `test:coverage`, `test:a11y`, `build`,
  plus der rote-vor-grün-Nachweis der drei Spezifikationsdateien.
- **#453:** `tsc -b`, `lint`, On-Prem-Lauf (Skip) **und** Cloud-Lauf (passed).
- **#462:** ruff/mypy/pytest plus der Diff-Grep, der leer sein muss.

## Abschluss

Ein Branch (`claude/autonomous-code-agent-role-s6x8z9`, wie vorgegeben), ein
Commit je Paket, ein PR mit fünf Closing-Keywords. Fünf kleine, klar getrennte
Commits bleiben in einem Zug lesbar; fünf PRs auf denselben vorgegebenen Branch
wären nicht möglich.

## Fortschritt

- [ ] #470
- [ ] #469
- [ ] #471
- [ ] #462
- [ ] #453

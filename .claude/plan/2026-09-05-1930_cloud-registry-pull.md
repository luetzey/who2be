# Cloud-Deploy zieht das CI-Image aus der Registry (WP-3 von #428, Issue #450)

- Status: **in Arbeit**
- Datum: 2026-09-05, 19:30 UTC (20. Lauf)
- Issue: #450 (`agent-ready`, `size/S`), Eltern-Issue #428
- Branch: `claude/autonomous-code-agent-role-u3thhe`

## 1. Ask-Once-Gate

**Bestanden.** Outcome, sechs von außen prüfbare Akzeptanzkriterien, explizites
Out-of-Scope, exakte Verifikations-Kommandos und fünf vorentschiedene Weichen
stehen vollständig im Issue-Body. Keine offene Weiche.

## 2. Muster-Entscheidung

**Keine Muster-Entscheidung nötig** — reine Infrastruktur-Konfiguration
(Compose-Overlay, Shell-Skript, Runbook). Es wird keine Struktur eingeführt,
die eine Abstraktion trüge; die fünf Design-Weichen sind im Issue entschieden.

## 3. Befund vor der Umsetzung: ein Prüfwert im Issue ist unerfüllbar

Das Verifikations-Kommando des Issues verlangt

```
grep -c 'pull_policy: build' docker-compose.cloud.yml            # 0
```

Das ist mit den eigenen Akzeptanzkriterien unvereinbar. AC 1 nennt
ausdrücklich nur `api` und `migrate` ("ist für **beide** Dienste entfernt").
Die Datei trägt aber **drei** Vorkommen — das dritte gehört `web`
(`docker-compose.cloud.yml:92`).

`web` kann nicht auf Registry-Pull umgestellt werden:

| Beleg | Fundstelle | Aussage |
|---|---|---|
| Build-Matrix der Pipeline | `.github/workflows/deploy.yml:17-44` | baut `api`, `web`, `mcp`, `api-cloud` — **kein** `web-cloud` |
| Das generische Web-Image | `.github/workflows/deploy.yml:31-35` | wird bewusst **ohne** `VITE_*`-Build-Args gebaut |
| Das Cloud-Overlay | `docker-compose.cloud.yml:87-92` | setzt `VITE_WHO2BE_EDITION: cloud` als Build-Arg |
| Grund | ADR-0029, Kommentar `:85-88` | die Billing-UI wird zur Compile-Zeit tree-geshaked; das On-Prem-Bundle enthält sie nicht |

Ein Registry-Pull für `web` würde der Cloud also die Billing-Oberfläche
nehmen. Ein `web-cloud`-Matrixeintrag wäre die Alternative — er läge in
`.github/workflows/deploy.yml`, und das ist im Issue **ausdrücklich
Out-of-Scope** ("die Pipeline baut und pusht bereits korrekt und wird nicht
angefasst").

**Entscheidung:** `web` behält `pull_policy: build`; der erwartete Grep-Wert
ist **1**, nicht 0. Belegt durch die Matrix oben — das ist eine Korrektur des
Prüfwerts, keine Scope-Änderung: die Akzeptanzkriterien bleiben unverändert
und werden vollständig erfüllt. Als Issue-Kommentar und im PR festgehalten.

**Nebenfund (eigenes Issue, nicht hier mitgefixt):** Overlay und Deploy-Skript
widersprechen sich heute bei `web`. Das Overlay erzwingt den lokalen Build
(`:92` plus Kommentar "erzwingt den lokalen Cloud-Build"), das Skript ruft
`compose pull web` mit der Begründung "es hat keine Cloud-Variante"
(`deploy/hetzner/scripts/deploy.sh:59-61`). Beides zugleich kann nicht stimmen;
faktisch gewinnt `pull_policy: build`, der Pull ist wirkungslos. Der Kommentar
im Skript ist damit irreführend.

## 4. Arbeitspaket (ein Paket, sequenziell)

1. `deploy/hetzner/who2be/docker-compose.cloud.yml` — `migrate` und `api` auf
   `image: ghcr.io/luetzey/who2be-api-cloud:${API_IMAGE_TAG}`, `build`-Block und
   `pull_policy: build` dort entfernt; `web` unverändert. Kommentare, die den
   lokalen Build begründen, auf den neuen Weg umschreiben.
2. `deploy/hetzner/scripts/deploy.sh` — Cloud-Zweig zieht `api migrate web`;
   der Kommentar, der den lokalen Cloud-Build begründet, wird ersetzt und
   benennt zugleich, warum `web` weiterhin lokal gebaut wird.
3. `deploy/hetzner/RUNBOOK.md` — neue Sektion "Notfallpfad: Registry nicht
   erreichbar" im Format der bestehenden Sektionen (Auslöser, Kommandos,
   Verifikation), plus Verweis auf den `DECISIONS.md`-Eintrag vom 2026-09-05
   und die GHCR-Login-Voraussetzung (Weiche 5).
4. `deploy/hetzner/README.md:267-274` — die Aussage, die Umstellung stehe aus,
   entfällt.
5. `CHANGELOG.md` (Unreleased) und `.claude/context/STATE.md` als letzter
   Commit (Sammelpunkt-Regel aus #442).

## 5. Verifikation (aus dem Issue, Grep-Wert korrigiert)

```bash
cd deploy/hetzner/who2be
docker compose -f docker-compose.yml -f docker-compose.cloud.yml --env-file ../.env.example config | grep -A3 -E '^\s+(api|migrate):'
grep -c 'pull_policy: build' docker-compose.cloud.yml            # 1 (web, siehe §3)
grep -n 'who2be-api-cloud' docker-compose.cloud.yml              # >= 1 Treffer
bash -n ../scripts/deploy.sh                                     # Syntax ok
grep -n 'Registry nicht erreichbar' ../RUNBOOK.md                # 1 Treffer
grep -n 'falls das Overlay spaeter auf Pull umgestellt' ../README.md   # kein Treffer mehr
```

Grün heißt: `config` zeigt für `api` und `migrate` ein `image:` aus GHCR und
keinen `build`-Kontext mehr; `web` behält seinen Build-Kontext.

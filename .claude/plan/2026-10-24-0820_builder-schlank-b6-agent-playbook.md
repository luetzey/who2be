# Builder schlank B6 — Teilabruf statt Teilen (Karte t_a4b4b9f8)

Neuer Zuschnitt: PM-Entscheidung 2026-10-24 (Option b) nach M1-Messung
(`builder-schlank-2026-10-nachher.md` §1.4, §3.3, §5.2). Die 25-KB-Grenze
entfällt; der erste Zuschnitt ist verworfen (siehe Schluss).

## Umgesetzt (Option b)
1. Profil-Laderegel `bp-p-output-load`: über der Warnschwelle
   (res-conv-h-laengen-budgets; Budgetzahlen leben nur in den Konventionen)
   erst outline, dann block_ids; geladene Konventions-Abschnitte nicht erneut holen.
2. Fall-Triage: `d7-h-wegweiser` + fertiger block_ids-Aufruf (Rahmen + ein Weg,
   Weg B + d7-h-a5).
3. Agent-PB tool_policy nur Feldbedeutung; Exklusiv-Fakten in res-conv-h-policy/-memory.
4. PB Persona lädt res-conv-h-sprache.
Nicht: Bündeln der 8 Lade-Sätze (16 Sidecars, sprengt Dateibudget 8).

## Messung DE und EN (b6_prozedur.py, Methodik prozedur.py, gegen Merge-Base db1b2912)
| Bau | DE vorher | DE nachher | DE Diff | EN vorher | EN nachher | EN Diff |
|---|---:|---:|---:|---:|---:|---:|
| Nur Persona | 13037 | 14283 | +1246 | 12794 | 14039 | +1245 |
| Agent bauen, minimal | 18609 | 17345 | −1264 (−6,8 %) | 17694 | 16564 | −1130 (−6,4 %) |
| Agent bauen, typisch (P+PB+A) | 43890 | 43872 | −18 | 42293 | 42408 | +115 |
| Fall-Triage ganz | 16894 | 17393 | +499 | 16426 | 16910 | +484 |
| Fall-Triage Weg A | 16894 | 11481 | −32,0 % | 16426 | 11214 | −31,7 % |
| Fall-Triage Weg B | 16894 | 12017 | −28,9 % | 16426 | 11602 | −29,4 % |
| Fall-Triage Weg C | 16894 | 10536 | −37,6 % | 16426 | 10157 | −38,2 % |
| Pflege, Feedback, External Tool | gleich | | 0 | gleich | | 0 |
| Konsistenz | 14128 | 14179 | +51 | 13976 | 14023 | +47 |
| Profil | 3241 | 3460 | +219 | 3073 | 3311 | +238 |

Typischer Agent-Bau mit „nicht erneut holen“ (jeder Abschnitt einmal):
DE −1485 B, EN −1427 B gegenüber der Zeile „typisch“.

## Verworfen

Der erste Zuschnitt (Commit 1e2ffbc1: Agent-Playbook teilen, neuer Abschnitt
res-conv-h-templates, harte 25-KB-Grenze) ist nach der PM-Entscheidung
2026-10-24 verworfen und per Folgecommit auf main-Stand zurückgesetzt.

# E5d · Änderung-Sheet lesend + Nachkontroll-Kennzahlen (t_e35428e0)

Basis `origin/main` b9f0b567. Spec: Neuschnitt `phase-e-web-neuschnitt-2026-10.md` §1, §2, §4, §7.1 (geht vor) + E5-Delta §0.4, §0.5, §4.1, §4.3, §8, §9.2.

## Fertig heißt
`/w/:ws/agents/:agentId/reviews/:sessionId?change=<id>` öffnet ein lesendes Sheet (rechts ab md, max. 40 rem; darunter Bottom-Sheet in voller Höhe) mit Feldern, Nachkontroll-Kennzahlen (erst ab Aktiviert) und Verlauf. `?change=first-due` löst nach dem Laden auf die erste fällige Änderung auf. Keine Aktionen (E5e).

## Dateien (7 / 8)
1. `apps/web/src/features/evolution/components/ChangeSheet.tsx` (neu)
2. `apps/web/src/features/evolution/components/ChangeSheet.test.tsx` (neu)
3. `apps/web/src/features/evolution/pages/ReviewDetailPage.tsx` (`?change=`, `first-due`, Fokus, Toast; Prüffälle als ganze Objekte)
4. `apps/web/src/features/evolution/pages/ReviewDetailPage.test.tsx`
5. `apps/web/src/i18n/locales/de.json`
6. `apps/web/src/i18n/locales/en.json`
7. `changelog.d/web-change-sheet.added.md`

## Entscheidungen (aus Karte/Spec, keine neuen Weichen)
- Eine Quelle je Ansicht (PM 2026-10-14): Zustand = `measure.state` vom Server, nie aus Events nachgerechnet. Die Fällig-Pill nutzt Datum + `followUp.ts` (an der einzelnen Änderung gibt es keinen Serverwert), aber den Server-Zustand für „abgeschlossen“/„noch nicht aktiv“. Liste und Sheet nutzen dieselbe Komponente.
- Kennzahlen-Request nur bei Server-Zustand ≥ Aktiviert (activated, follow_up_prepared, effective, ineffective, not_measurable) bzw. `withdrawn` mit `activated` im Verlauf.
- Begriffe nach A4a (Neuschnitt §1): Maßnahme → Änderung, Fälle → Rückmeldungen, Nachschau → Nachkontrolle, Versionsstatus „Zur Freigabe“; Keys nach E5-Delta §9.2.
- „je 100“ rechnet die UI aus Rohzahlen (QE8 a), eine Nachkommastelle; Richtung nur als Wort; bei `insufficient` keine Richtung bei der Rate, dafür `followUp.tooFewUses`.
- `activated` mit Zahl nur, wenn `metrics.count` eine Zahl ist; der Server liefert heute keine (version_status.py), also greift `activatedNoCount`.
- Unbekanntes Event: „Ereignis“ statt „Änderung“ (A4a belegt „Änderung“ mit der Maßnahme).
- Overflow-Regressionstest in Vitest über Klassen (Muster `PlaybookRow.responsive.test.tsx`), echte Breiten in `measure.json` der Fotos mit langen Namen/URLs.

## Verifikation
`npx tsc -b`, `npm run lint`, `npm run i18n:check`, `npm run test:coverage`, `npm run build`, `npm run license:check`; Mutationen (Gate vor Aktiv, Server-Zustand vs. Events); Fotos 1280/390 × hell/dunkel × editor/viewer.

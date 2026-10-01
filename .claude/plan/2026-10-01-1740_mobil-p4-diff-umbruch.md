# Mobil P4: Versionsvergleich bricht um (Spec M4, W2=a)

Karte t_88035a98 · Spec `/home/luetzey/recherche/mobile-spec-2026-09-29.md`
M4, §3 (P4: `components/version/VersionDiffView.tsx` + Test), §4 W2=a.
Basis: origin/main 67718ef2.

## Completion-Condition

- Im Text-Diff gibt es kein Element mit `scrollWidth > clientWidth` bei
  320/390/430/1280, gemessen in Chromium gegen das gebaute Stylesheet.
  Ausgenommen sind die `sr-only`-Präfixe (1 px, `overflow:hidden`, kein
  Scroller und nicht sichtbar).
- Jede Diff-Zeile ist ein Grid `grid-cols-[1.25rem_1fr]`: links die
  Plus/Minus-Rinne, rechts der Text mit `whitespace-pre-wrap wrap-anywhere`.
  Umbrochene Folgezeilen stehen unter dem Text, nicht unter dem Zeichen.
- Es gibt kein `overflow-x-auto` und kein `min-w-max` mehr. W2=a gilt auf
  allen Breiten, auch ab `md` gibt es keine zweite Darstellung.
- Die Screenreader-Präfixe `diff.lineAdded`/`lineRemoved` bleiben. Das Zeichen
  `+`/`-` bleibt sichtbar, Farbe ist also nicht das einzige Merkmal.
- Vitest mit Rot-Probe. Web-DoD: lint, tsc -b, i18n:check, test:coverage,
  build, license:check. E2E-Fall M4 in `scroll-guard.spec.ts`,
  Changelog-Fragment, höchstens 8 Dateien, CI grün.

## Entscheidungen

- Das Zeichen bleibt `-` wie bisher, kein Wechsel auf `−`. Es ist
  `aria-hidden`, und ein Wechsel wäre eine kosmetische Änderung außerhalb der
  Spec.
- Die Rinne bekommt `select-none`, damit beim Kopieren eines Diff-Abschnitts
  der Text ohne `+`/`-` in die Zwischenablage kommt. Der Hunk-Kopf war schon
  `select-none`.
- Die Hunk-Kopfzeile bekommt ebenfalls `wrap-anywhere`. Sie ist kurz, aber bei
  320 px sonst die nächste mögliche Ursache für Überlauf.
- Am Wrapper steht kein `overflow-hidden`. Das würde einen Überlauf verdecken
  statt ihn zu beheben.

## Schritte

1. [x] Vorher-Messung, Markup-Probe gegen dist-CSS: Wrapper 9.189/208 px bei
   320, bei 390/430/1280 ebenso 9.189 px Scrollweite.
2. [x] Umbau `VersionDiffView.tsx`.
3. [x] Vitest (Klassenvertrag + Struktur) mit Rot-Probe: Komponente von
   origin/main ergibt 3 rote Tests, ohne `wrap-anywhere` 1 rot, mit
   `overflow-x-auto` zurück 1 rot.
4. [x] E2E-Fall M4 in `scroll-guard.spec.ts`: 4/4 Profile grün. Rot-Probe
   gegen ein Image von origin/main: 4/4 rot (Wrapper 8.382 px bei 210/280/
   444/440 px).
5. [x] Nachher-Messung, Screenshots hell/dunkel, DoD, Changelog, PR.

## Messung im echten Stack (Persona, 1.100-Zeichen-Beschreibung + URL, de)

| Breite | Vorher Wrapper scroll/client | Nachher | Diff-Höhe vorher → nachher |
|---|---|---|---|
| 320 | 8.980 / 210 | 210 / 210 | 130 → 1.330 px |
| 390 | 8.980 / 280 | 280 / 280 | 130 → 990 px |
| 430 | 8.980 / 320 | 320 / 320 | 130 → 850 px |
| 1280 | 8.980 / 440 | 440 / 440 | 130 → 570 px |

Im Diff gibt es danach kein Element mehr mit eigener Scrollweite (ohne die
1-px-`sr-only`-Präfixe), und der Body scrollt auf keiner Breite horizontal.
Die Rinne ist 20 px breit, der Text beginnt bei 28 px. Hell und dunkel
verhalten sich gleich. Die Höhe wächst bewusst: Der Text ist jetzt
vollständig lesbar statt abgeschnitten (Spec: „nur in eine Richtung
scrollen“).

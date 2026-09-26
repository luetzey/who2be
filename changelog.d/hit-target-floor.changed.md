- Der Hit-Target-Floor der Design-Language steht jetzt an genau einer Stelle.

  §11 (A11y-Minimum) in `docs/frontend/design-language.md` benennt den Floor
  explizit: verbindlich sind **≥ 32px** (HIG), alles darueber ist Praeferenz —
  `size="default"` (40px) als Regelfall, 44px als Mobile-Praeferenz,
  `size="sm"` (36px) zulaessig, aber nicht Default. Bisher war der Floor nur in
  einer Klammer angedeutet.

  Die Responsive-Checkliste in §4.4 forderte im selben Atemzug "≥ 40px (§11
  A11y-Minimum)" und erklaerte damit den `default`-Wert faelschlich zum
  Minimum. Sie zitiert §11 jetzt korrekt und setzt keine eigene Zahl mehr.
  Reine Doku-Klarstellung, keine Code-Aenderung: bestehende `size="sm"`-Hits
  (36px) lagen nie unter dem Floor.

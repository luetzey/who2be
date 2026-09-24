- `PopoverContent` begrenzt seine Hoehe auf den verfuegbaren Platz und laesst zu
  hohen Inhalt in sich scrollen. Auf Phone-Breite fiel der Fuss langer Popover
  (z. B. der Bestaetigen-Button des ResourcePickers) unter die Viewport-
  Unterkante und war nicht mehr klickbar.

  Das Primitive kappte bisher nur die Breite (`max-w-[calc(100vw-1rem)]`); ein
  Gegenstueck fuer die Hoehe fehlte — anders als in `DialogContent`, das
  `max-h` + `overflow-y-auto` seit jeher traegt. Neu ist
  `max-h-[var(--radix-popover-content-available-height)] overflow-y-auto`: die
  Variable liefert Radix' `size`-Middleware mit dem tatsaechlich verfuegbaren
  Platz (inkl. Ankerposition und `collisionPadding`), eine feste `vh`-Pauschale
  koennte das nicht. Gemessen auf 320px: 234px verfuegbar bei einem Panel, das
  bei y = 326px beginnt. Scrollen half nicht, weil der Popper-Wrapper
  `position: fixed` ist.

  Die Begrenzung wirkt fuer alle 17 Importstellen des Primitives. Der
  Handkompensator in `PlaceholderHelp.tsx` (`max-h-[70vh] overflow-auto`) ist
  damit redundant und entfaellt — `70vh` waere dort sogar grosszuegiger als der
  real verfuegbare Platz. Aufrufer-`max-h-*` gewinnt weiterhin ueber
  tailwind-merge; `popover.test.tsx` haelt beides fest.

- Lange Beschreibungen stehen auf dem Telefon gekürzt im Detailkopf, mit
  „Mehr anzeigen“ zum Aufklappen im Seitenfluss (Mobil-Spec M2/M8). Vorher
  belegte eine lange Beschreibung bei 320 px bis zu 1.600 px, die Tabs mit dem
  eigentlichen Inhalt lagen erst nach bis zu 2,8 Bildschirmen.

  Neue Komponente `ExpandableText` (`apps/web/src/components/data/`): kürzt
  auf N Zeilen (Detailkopf 3 unter `md`, 6 ab `md`) mit dem präfixierten
  `-webkit-line-clamp`-Muster und zeigt den Knopf nur, wenn gemessen
  tatsächlich gekürzt wird — ein `ResizeObserver` misst bei Drehung und
  Textzoom neu. Der Knopf ist ein echter Button mit `aria-expanded` und
  `aria-controls`, mit 44 px Trefferfläche unter `md`; der gekürzte Text bleibt
  vollständig im DOM. Aufgeklappt wächst die Seite, es gibt keinen inneren
  Scrollbereich.

  Der Legacy-System-Prompt-Hinweis in der Persona scrollt nicht mehr in sich
  (`max-h-40 overflow-auto`, bei 320 px 160 px sichtbar von 3.312 px), sondern
  steht gekürzt auf 6 Zeilen im Seitenfluss.

  Die `common`-Schlüssel der Mobil-Spec liegen gesammelt an
  (`actions.showMore`, `actions.showLess`, `actions.showMoreCount`,
  `list.shownOfTotal`, `table.scrollHint`, `tabs.detailViewAria`); die vier noch
  ungenutzten stehen bis zu ihren Folgepaketen in der Waisen-Baseline.

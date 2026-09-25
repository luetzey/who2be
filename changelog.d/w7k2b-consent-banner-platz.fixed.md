- Das Cookie-Consent-Banner reserviert den Platz, den es belegt, statt den
  Seitenfuss zu ueberlagern. Auf schmalen Viewports war die primaere
  Formularaktion darunter nicht mehr erreichbar.

  Das Banner meldet seine per `ResizeObserver` **gemessene** Hoehe als
  `--cookie-banner-height` an das Dokument; `globals.css` verbraucht den Wert
  in `body { padding-bottom }` (der Inhalt endet nicht mehr unter dem Banner)
  und `html { scroll-padding-bottom }` (ein `scrollIntoView` legt sein Ziel
  nicht mehr unter das `fixed` Element, CSS Scroll Snap Level 1 §4.2). Eine
  feste Hoehe waere falsch gewesen: gemessen sind es je nach Profil 150px
  (Desktop/Tablet), 226px (iPhone 13) und 266px (320px), weil die Karte
  unterhalb `sm` stapelt. Nach der Entscheidung faellt die Variable weg, beide
  Regeln fallen auf `0px`.

  Das Consent-Verhalten ist unveraendert: Opt-in bleibt Opt-in, das Banner
  bleibt bis zur Entscheidung sichtbar, kein Tracking ohne Zustimmung,
  tab-uebergreifende Synchronisierung intakt. Ein neuer E2E-Spec
  (`apps/web/e2e/consent-overlay.spec.ts`) haelt den Fall dauerhaft unter Test
  und raeumt das Banner dabei bewusst **nicht** weg.

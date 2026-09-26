- Die E2E-Journeys pruefen an fuenf Stationen (Login, Impressum,
  Persona-Formular, Persona-Detail, Playbook-Formular, Resource-Detail mit
  Editor), dass die Seite nicht horizontal scrollt.

  Der Helfer `expectNoHorizontalScroll` (`apps/web/e2e/helpers/viewport.ts`)
  vergleicht `documentElement.scrollWidth` mit `clientWidth` und nennt beim
  Fehlschlag die ueberlaufenden Elemente mit Selektor, rechter Kante und
  `position` — eine nackte Breitenmeldung verschweigt den Ort des Defekts.
  Elemente innerhalb eines Vorfahren mit computed `overflow-x`
  `auto`/`scroll`/`hidden` gelten nicht als Verursacher; das deckt die bewusst
  scrollbaren Bereiche ab (Tabellen-Wrapper). Ein eigener Spec
  (`e2e/scroll-guard.spec.ts`) haelt Erkennung und Nicht-Fehlalarm dauerhaft
  unter Test.

- Der Test-Helfer `decideCookieConsent` liegt jetzt unter
  `apps/web/e2e/helpers/consent.ts` und wird in allen E2E-Tests mit
  `page`-Fixture angewandt statt nur in der Billing-Spec.

  Das Consent-Banner faengt auf schmalen Viewports Klicks auf die primaeren
  Buttons ab; die Mobile-Profile liefen dadurch in Test-Timeouts. Der Helfer
  entscheidet vor der ersten Navigation auf `rejected` (datensparsam, kein
  Analytics noetig). Er ersetzt **keinen** Fix des Banners — dass es auf einem
  320-px-Geraet den primaeren Button unerreichbar macht, bleibt ein
  Anwendungsdefekt und wird getrennt behandelt.

- Lange Beschreibungen und Trigger mit URL ohne Trennstelle lassen auf dem
  Telefon keine Seite mehr seitlich scrollen (WCAG 1.4.10 Reflow, Mobil-Spec
  M1/M12). Gemessen waren bei 320 px bis zu 1.091 px Seitenbreite auf
  Persona-, Agent-, System-Prompt- und Playbook-Detail sowie der
  Playbook-Liste.

  Ursache war die min-content-Breite der langen URL: das Kopf-`<p>` in
  `DetailHeader` (und die eigenen Koepfe/Zeilen der Playbooks) hatte keine
  Umbruchregel, und die Flex-Kette reichte die Wortbreite bis zum Dokument
  durch. Beschreibung, Playbook-Kopf, Playbook-Zeile und deren Trigger-Pillen
  tragen jetzt `wrap-anywhere`. Ein Chip im Tag-Feld (`TagInput`) wird bei
  langem Text mehrzeilig statt Feld und Karte zu sprengen; das Entfernen-X
  bleibt oben rechts, die Ecken sind `rounded-xl` statt Pille, damit ein
  mehrzeiliger Chip kein Oval wird.

  Als Netz fuer kuenftige Stellen setzt das Basis-Stylesheet
  `p, li, dd, td { overflow-wrap: break-word; }`. Das faengt sichtbaren
  Ueberlauf ab, aendert aber keine Spaltenbreiten; Stellen, deren Spalte sich
  an der Wortbreite aufblaeht, brauchen weiter `wrap-anywhere` am Element.

  `apps/web/e2e/scroll-guard.spec.ts` legt Persona, Playbook, Resource,
  System-Prompt, Tool und Agent mit so einer URL an und prueft Liste und
  Detailseite auf allen vier Playwright-Profilen auf horizontalen Body-Scroll
  sowie den Trigger-Chip auf Verbleib im Viewport.

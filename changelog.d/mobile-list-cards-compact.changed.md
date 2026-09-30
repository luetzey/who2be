- Listenkarten auf dem Telefon sind kompakt (Mobil-Spec M3/M6). Die
  Beschreibung in `EntityCard` (Personas, Resources, System-Prompts, Agents und
  weitere Listen) und in der Playbook-Zeile ist auf 2 Zeilen unter `md` und 3 ab
  `md` gekürzt, harte Kürzung mit „…“. Einen „Mehr anzeigen“-Knopf pro Karte
  gibt es nicht: Die ganze Karte ist ein Link zur Detailseite mit dem Volltext.
  Der Text bleibt vollständig im DOM, ein Screenreader liest also alles vor.
  Vorher war eine Karte mit langer Beschreibung bei 320 px bis zu 4 Bildschirme
  hoch.

  Unter `md` steht die Icon-Kachel klein (32 px) in der Titelzeile, damit die
  Textspalte die volle Kartenbreite nutzt (vorher 162 px bei 320 px). In der
  aufklappbaren Zusammenfassung (Sub-Playbooks, Sub-Resources) steht unter `md`
  nur die Anzahl, also etwa „6 Sub-Playbooks“. Die Namensliste kommt ab `md`
  dazu und hat dort mindestens 96 px Breite. Vorher hatte sie bei 320 px noch
  17 px, also nur eine Ellipse.

# Gestaltung, Zustände, Barrierefreiheit, Verhalten

> Teil der Website-Spezifikation, siehe [`README.md`](README.md).
> Die App-Designsprache steht in
> [`../frontend/design-language.md`](../frontend/design-language.md) und gilt
> dort verbindlich. Diese Datei sagt, was die **Website** davon übernimmt und
> wo sie bewusst abweicht.

## 1 · Verhältnis zur Designsprache „Warm Citrus"

Die Website soll aussehen wie das Produkt, in das sie führt — sonst wirkt der
Klick auf „Kostenlos ausprobieren" wie ein Sprung zu einem anderen Anbieter.
Deshalb: **übernehmen, wo es um Erscheinung geht; nicht übernehmen, wo es um
die React-Technik geht.**

### Übernommen (unverändert)

| Sache | Quelle | Bemerkung |
|---|---|---|
| Farbwerte in OKLCH, Markenfarbe `oklch(0.72 0.17 55)` hell / `oklch(0.74 0.17 55)` dunkel, Text darauf `oklch(0.985 0 0)` bzw. `oklch(0.145 0 0)`, Hover `oklch(0.66 0.17 55)` / `oklch(0.80 0.16 55)` | §2.2 | Der Coder kopiert die Werte aus `apps/web/src/styles/globals.css` in die Website-Tokens. **Kein Hex im Markup.** |
| Flächen-Hierarchie Hintergrund / Karte / Schwebefläche | §2.3 | Hell über Schatten, dunkel über drei Helligkeitsstufen |
| Schatten-Stufen `card` / `popover` / `modal` | §2.5 | |
| System-Schriftstapel, **kein Web-Font-Download** | §3.1 | Wirkt doppelt: kein Layoutsprung, kein Drittanbieter-Abruf — deshalb auch kein Cookie-Banner nötig |
| Schriftgrößen-Skala, `tracking-tight` ab `text-xl`, Eyebrow als `text-xs uppercase tracking-wide` | §3.2–3.4 | |
| 4-px-Raster, erlaubte Abstufungen `1,2,3,4,6,8,12,16` plus `10` nur für Seiten-Vertikalabstand | §4.1 | |
| Breakpoint-Skala `sm` 640 / `md` 768 / `lg` 1024 / `xl` 1280, mobil zuerst | §4.4 | |
| Radien: 6 px Knöpfe/Eingaben, 8 px kleine Flächen, 12 px Karten | §5 | |
| Bewegungsdauern 120 / 200 / 320 ms, die drei Easing-Kurven, `prefers-reduced-motion` respektieren, **nie** `transition-all` | §7 | |
| Icon-Satz Lucide, Strichstärke 2, Icons nie in der Markenfarbe | §8 | |
| **Genau eine** Aktion in der Markenfarbe pro Fläche | §2.2, §13.4 | Auf der Startseite: Hero-Knopf und Abschluss-Knopf sind zwei getrennte Flächen, die Kopfzeile eine dritte |
| Stimme: sachlich, knapp, Du-Form, Volltext-Umlaute, kein Marketing-Geschwurbel, Knöpfe im Infinitiv | §1 | Deckt sich mit dem Rechercheergebnis (Marketing-Sprache messbar schädlich) |

### Bewusste Abweichungen

| Abweichung | Was die App macht | Was die Website macht | Begründung |
|---|---|---|---|
| Container-Breite | Verwaltungsseiten `max-w-5xl` (1024 px) | Textabschnitte `max-w-3xl` (768 px), Rasterabschnitte `max-w-5xl` | §4.2 sieht für Marketing-Seiten ausdrücklich `max-w-md` bis `max-w-3xl` vor. Fließtext über 1024 px ist schlecht lesbar (Zeilen zu lang) |
| Größte Schriftgrade | `text-3xl` bis `text-5xl` sind „Reserve" für Marketing | H1 der Startseite nutzt `text-4xl`, ab `md` `text-5xl`; H1 der Unterseiten `text-3xl`, ab `md` `text-4xl` | §3.2 gibt diese Grade für Marketing-Seiten frei. Damit ist der Reserve-Fall eingetreten |
| Technik | React, Tailwind, shadcn, `cva`-Varianten | Statisches HTML, keine Komponentenbibliothek, kein React | Owner-Entscheidung (eigene statische Seite). Die Website bildet das *Erscheinungsbild* mit eigenem CSS nach, sie importiert nichts aus `apps/web/` |
| Glas-/Unschärfe-Effekte | ausgeschlossen (§6) | bleiben ausgeschlossen | Die Begründung (Kosten) gilt hier genauso, und die Zielgruppe belohnt Effekte nicht |
| Erfolgs-/Warnfarben | werden erst bei echtem Bedarf eingeführt (§2.4) | kein Bedarf, also keine | Die Website hat keine Zustände, die Erfolg oder Warnung meldeten |

**Nicht geteilt wird Code.** Kein Import aus `apps/web/`, keine gemeinsame
Tailwind-Konfiguration, kein Monorepo-Paket für Tokens. Begründung: Die
Kopplung wäre teurer als die Duplikation von rund 30 Farbwerten, und die
Website soll sich ohne App-Build bauen lassen. Der Coder legt die Tokens in
**einer** CSS-Datei ab, mit einem Kommentarkopf:

```
/* Werte gespiegelt aus apps/web/src/styles/globals.css (Designsprache
   docs/frontend/design-language.md). Bei Änderung dort hier nachziehen —
   bewusst kopiert, nicht importiert (kein Build-Abhängigkeit zur App). */
```

## 2 · Hell und dunkel

- Die Website folgt `prefers-color-scheme` und bietet **keinen** Umschalter.
- Begründung: Ein Umschalter braucht Speicherung im Browser, damit er
  überlebt — das ist die einzige Speicherung, die die Website sonst gar nicht
  bräuchte, und sie zöge einen Satz in der Datenschutzerklärung nach sich.
  Die Systemeinstellung trifft die Präferenz in fast allen Fällen richtig.
- Beide Modi werden gleichwertig geprüft. Dunkel ist kein Nachgedanke.

## 3 · Kontraste und Barrierefreiheit (Ziel: WCAG 2.1 AA)

| Anforderung | Umsetzung |
|---|---|
| Text-Kontrast ≥ 4,5:1, große Schrift (ab 24 px bzw. 19 px fett) ≥ 3:1 | Markenfarbe zu Text darauf ist in der App verifiziert (§11). Für jede **neue** Kombination der Website (z. B. gedämpfter Text auf gedämpfter Fläche) rechnet der Coder den Wert nach und hält ihn in einem kurzen Prüfprotokoll fest |
| Nicht-Text-Kontrast ≥ 3:1 | Knopfränder, Eingabe-Ränder, Fokus-Ring, die Pfeile der Ablauf-Skizze |
| Farbe nie die einzige Information | Die hervorgehobene Pro-Karte trägt zusätzlich das Textkennzeichen „Empfohlen für laufenden Betrieb"; die aktive Navigation trägt `aria-current` |
| Fokus sichtbar | Ring in der neutralen Ring-Farbe, **nicht** in der Markenfarbe (§11). Nie `outline: none` ohne Ersatz |
| Überschriften-Ordnung | Genau eine `h1` je Seite, danach lückenlos `h2`, `h3` — keine Sprungebene, keine Überschrift, die nur größer aussehen soll |
| Sprunglink | Erster fokussierbarer Inhalt jeder Seite: **„Zum Inhalt springen"** auf `#inhalt`, unsichtbar bis Fokus |
| Landmarken | `header`, `nav`, `main id="inhalt"`, `footer`. Die Fußzeilen-Navigation hat `aria-label="Fußzeile"`, die Hauptnavigation `aria-label="Hauptnavigation"` |
| Bedienflächen | mindestens 40 × 40 px, unter `md` bevorzugt 44 px (§11) |
| Sprache | `<html lang="de">`. Einzelne englische Begriffe im Text (Docker-Befehle, Produktnamen) brauchen keine Auszeichnung; ein vollständiger englischer Satz wäre mit `lang="en"` auszuzeichnen — kommt in diesen Texten nicht vor |
| Bilder | Die einzige Grafik ist die Ablauf-Skizze als Inline-SVG mit `role="img"` und `<title>`. Rein dekorative Elemente (falls Trennlinien als SVG) `aria-hidden="true"` |
| Bewegung | Keine automatisch startende Bewegung, kein Karussell, kein Parallax. `prefers-reduced-motion: reduce` kappt alle Übergänge auf nahezu null (Regel wie in der App) |
| Zoom | Bei 200 % Textzoom bleibt jede Seite bedienbar, ohne dass Inhalt abgeschnitten wird. Keine `maximum-scale`- oder `user-scalable=no`-Angabe im Viewport-Tag |
| Tests | Ein automatischer Barrierefreiheits-Durchlauf (axe oder gleichwertig) je Seite in der Bau-Pipeline, plus eine Tastatur-Durchquerung je Seite von Hand |

### Tastatur-Durchquerung — erwartete Reihenfolge

Startseite, von oben:
1. „Zum Inhalt springen"
2. Wortmarke
3. Funktionen, Selbst betreiben, Dokumentation, Preise
4. „Kostenlos ausprobieren" (Kopfzeile)
5. Hero: „Kostenlos ausprobieren", „Selbst betreiben"
6. weiter in Leserichtung durch die Abschnitte
7. Fußzeilen-Links spaltenweise

Unter `md` schiebt sich der Knopf des Mobil-Menüs zwischen 2 und 3; ist das
Menü zu, sind die Navigationslinks **nicht** fokussierbar (`inert` oder
tatsächlich nicht gerendert) — ein geschlossenes Menü mit erreichbaren Links
ist der häufigste Tastaturfehler bei solchen Seiten.

## 4 · Handy und Desktop

Prüflinien: **320, 375, 768, 1024, 1280 px** (§4.4 der Designsprache).

| Abschnitt | < 640 px | 640–1023 px | ≥ 1024 px |
|---|---|---|---|
| Kopfzeile | Wortmarke + Menü-Knopf + „Ausprobieren" | wie Desktop, engere Abstände | volle Navigation |
| Hero | einspaltig, H1 `text-4xl`, Knöpfe gestapelt und vollbreit | H1 `text-5xl`, Knöpfe nebeneinander | wie 640–1023, breitere Ränder |
| Ablauf in vier Schritten | einspaltig untereinander | 2 × 2 | 2 × 2 oder 4 × 1, je nach Zeilenlänge — nicht schmaler als 240 px je Spalte |
| Funktionsraster | eine Spalte | zwei Spalten | drei Spalten |
| Zwei Wege | untereinander, Selbst-Betreiben zuerst | nebeneinander | nebeneinander |
| Preiskarten | untereinander, Pro zuletzt | zwei Spalten, dritte umbricht | drei Spalten |
| Preisvergleichstabelle | waagerecht scrollbarer Container mit `tabindex="0"` | wie Desktop | wie Desktop |
| Codeblöcke | waagerecht scrollbar, kein Umbruch | wie Handy | wie Handy |
| Fußzeile | Spalten untereinander | zwei Spalten | drei Spalten |

**Regeln, die im Review geprüft werden** (aus §4.4 der Designsprache
übernommen):
1. Bei 320 px kein waagerechtes Scrollen der Seite — nur die ausdrücklich
   scrollbaren Container (Tabelle, Codeblock).
2. Jedes Raster ab zwei Spalten hängt an einem Breakpoint-Präfix, nie nackt.
3. Feste Breiten auf Container-Ebene sind responsiv abgefedert.
4. Bedienflächen bleiben unter `md` mindestens 40 px hoch.
5. Text bleibt bei 320 px lesbar, keine abgeschnittenen Beschriftungen.
6. 768 px und 1024 px werden stichprobenartig mitgeprüft, nicht nur die
   Extreme.

Das Mobil-Menü ist ein Ausklapp-Bereich unter der Kopfzeile, **kein**
Bildschirm-Vorhang. Begründung: vier Links brauchen kein Vollbild, und ein
Vorhang braucht Fokus-Falle plus Escape-Behandlung — Aufwand ohne Gewinn. Der
Knopf trägt `aria-expanded` und `aria-controls`; er funktioniert mit einem
`<details>`-Element auch ohne JavaScript.

## 5 · Langsame Verbindung und Fehlerfälle

Die Website hat keine Daten, die laden könnten — es gibt also keine
Ladezustände im üblichen Sinn. Was es dennoch braucht:

| Fall | Verhalten |
|---|---|
| Langsame Verbindung | Der erste Bildschirm besteht ausschließlich aus HTML und CSS. Kein Bild, kein Web-Font, kein JavaScript im kritischen Pfad — der Hero ist sichtbar, sobald das HTML da ist. Zielwerte: HTML jeder Seite unter 50 KB, CSS unter 20 KB, JavaScript insgesamt unter 5 KB |
| JavaScript aus oder fehlgeschlagen | Jeder Inhalt und jeder Link funktioniert. Verloren gehen nur: der „Kopieren"-Knopf an Codeblöcken (wird dann nicht gerendert) und die Animation des Mobil-Menüs (das `details`-Element klappt trotzdem) |
| CSS fehlgeschlagen | Die Seite bleibt lesbar, weil die Struktur semantisch ist: Überschriften, Listen, Tabellen mit Zeilenköpfen. Kein Inhalt lebt in Pseudo-Elementen |
| Externe Ziele nicht erreichbar (App, Repo) | Die Website merkt das nicht und soll es nicht prüfen. Aber: `PUBLIC_APP_URL` ist Bau-Pflicht — fehlt sie, bricht der Bau ab, statt einen Knopf ins Leere auszuliefern |
| Tote Links | Ein Link-Prüfer läuft in der Bau-Pipeline über alle internen Links und meldet Fehler als Baufehler. Begründung: „Typographical errors and broken links hurt a site's credibility more than most people imagine" (Stanford) |
| Tippfehler | Ein Rechtschreibprüfer für Deutsch läuft über die Textdateien. Dieselbe Begründung |
| Druck | Ein schmales Druck-Stylesheet: Kopf- und Fußzeilennavigation ausblenden, Linkziele hinter dem Linktext ausgeben, Seitenumbrüche nicht mitten in Abschnitten. Relevant, weil Abschnitt 8 der Startseite und die Preisseite die Dinge sind, die jemand ausdruckt oder als PDF weitergibt |

Zusätzlich: `Content-Security-Policy` ohne `unsafe-inline`, keine Verbindungen
zu Dritten (`connect-src 'none'`, `img-src 'self'`). Das ist keine
Design-Vorgabe, aber es sichert die Aussage „keine Cookies, keine
Analysewerkzeuge" technisch ab, auf die sich die Datenschutzerklärung stützt.

## 6 · Was ausdrücklich nicht gebaut wird

| Nicht bauen | Grund |
|---|---|
| Karussell, Ticker, automatisch wechselnde Inhalte | Kein Inhalt, der es trägt; schadet Lesbarkeit und Barrierefreiheit |
| Einblendungen beim Scrollen („fade in on scroll") | Verzögert den Inhalt für eine Zielgruppe, die scannen will (Nielsen: knappe, scannbare Fassung messbar besser) |
| Overlay beim Verlassen der Seite, Newsletter-Kasten, Chat-Widget | Aggressive Kommerzialität ist messbar glaubwürdigkeitsschädlich (Stanford CHI 2001) |
| Cookie-Banner | Nicht erforderlich, weil nichts gesetzt wird — und ein Banner ohne Notwendigkeit ist ein selbstgemachter Schaden |
| Nutzerzahlen, Logo-Leiste, Bewertungssterne | Existieren nicht. Erfundener Sozialbeweis ist Betrug |
| Produktschnappschüsse als Rasterbilder | Bewusst offen gelassen: echte Bildschirmbilder wären wertvoll, veralten aber bei jeder UI-Änderung und wiegen viel. Empfehlung für eine Folgekarte: **zwei** Bildschirmbilder (Versionsvergleich, Agenten-Detail) in WebP mit `loading="lazy"`, feste Breiten-/Höhenangabe gegen Layoutsprung, Alternativtext, der beschreibt was zu sehen ist. Solange sie fehlen, funktioniert die Seite — deshalb keine Bau-Voraussetzung |
| Video | Gleiche Begründung, höhere Kosten |

## 7 · Abnahme-Liste für den Bau

Die Seite ist fertig, wenn alle Punkte grün sind:

1. Alle fünf Seiten erreichbar, 404 liefert Status 404, alle Weiterleitungen aus
   `weitere-seiten.md` §7 greifen.
2. Kein Text auf einer Seite weicht von dieser Spezifikation ab; kein
   Platzhalter im gerenderten HTML.
3. Jede Funktionsaussage steht in der Belegtabelle (`README.md` §3).
4. Free-/Pro-Zahlen stimmen mit `plans.py` und `entitlement.py` überein;
   `/preise` ist ohne Anmeldung erreichbar.
5. Impressum und Datenschutzerklärung enthalten die vom Owner gelieferten
   Angaben — vollständig, ohne Platzhalter.
6. Barrierefreiheits-Durchlauf je Seite ohne Befund; Tastatur-Durchquerung je
   Seite von Hand geprüft, Reihenfolge wie §3.
7. 320 / 375 / 768 / 1024 / 1280 px geprüft, hell und dunkel.
8. Bei 200 % Textzoom bleibt jede Seite bedienbar.
9. JavaScript deaktiviert: alle Inhalte und Links funktionieren.
10. Link-Prüfer und Rechtschreibprüfung laufen im Bau und sind grün.
11. Kein Netzwerkaufruf an einen Dritten beim Laden einer Seite (im
    Netzwerk-Fenster des Browsers geprüft).
12. `PUBLIC_APP_URL` führt in eine Cloud, in der die Registrierung offen ist
    (`WHO2BE_LAUNCH_MODE` nicht `coming_soon`) und Google sowie GitHub als
    Anmeldewege bereitstehen.

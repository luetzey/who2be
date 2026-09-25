# Startseite — Abschnitt für Abschnitt

> Teil der Website-Spezifikation, siehe [`README.md`](README.md).
> Alle Texte sind **fertig** und werden wortgleich übernommen.
> Motiv-Bündel A–D nach Recherchebericht §1.3:
> **A** „Ich will die Routine los" (80 %/72 %) · **B** „Ich will, dass es jedes
> Mal gleich läuft" · **C** „Ich verliere den Überblick" (unbelegt) ·
> **D** „Ich muss es jemandem erklären können".

## Reihenfolge im Überblick

| # | Abschnitt | Bündel | Entkräfteter Einwand |
|---|---|---|---|
| 0 | Kopfzeile mit Navigation | — | „Wo finde ich die Doku?" |
| 1 | Hauptaussage (Hero) | A, dann B | „Noch ein Agenten-Baukasten" |
| 2 | Das Problem in drei Sätzen | A | „Mein Problem ist ein anderes" |
| 3 | Was Who2Be ist — in einem Satz und einem Bild | A + B | „Was genau ist das Ding?" |
| 4 | Der Ablauf in vier Schritten | B | „Wie greift das in meine Arbeit?" |
| 5 | Was drin ist (Funktionsraster) | A, B, C | „Reicht das für meinen Fall?" |
| 6 | Zwei Wege: selbst betreiben oder Cloud | A + D | „Muss ich meine Prompts hochladen?" |
| 7 | Was beim ersten Klick passiert | A | „Werde ich gleich zur Kasse gebeten?" |
| 8 | Für die Leute, die es freigeben müssen | D | „Was sage ich meinem Chef / meiner IT?" |
| 9 | Ehrliche Lage | A, B, D | „Wer nutzt das überhaupt?" |
| 10 | Preise kurz | A | „Was kostet es wirklich?" |
| 11 | Häufige Fragen | A, B, C, D | die restlichen Einwände, knapp |
| 12 | Abschluss-Aufforderung | A | letzter Anker |
| 13 | Fußzeile | D | Rechtliches, Quellcode, Lizenz |

Begründung der Reihenfolge: Ziel vor Mechanismus (Bündel A vor B, Bericht §3),
Beweismaterial und Entscheider-Stoff nach unten gestaffelt (Bericht §2.3
„eine Seite, zwei Rollen, unterschiedliche Tiefe"), Preise doppelt — kurz auf
der Startseite und vollständig auf `/preise` (Preistransparenz, TrustRadius).
Kein Abschnitt fragt den Besucher, wer er ist (NN/g: „Users don't know which
group to choose").

---

## 0 · Kopfzeile

```
┌───────────────────────────────────────────────────────────────────────┐
│ Who2Be        Funktionen  Selbst betreiben  Dokumentation  Preise     │
│                                          [ Kostenlos ausprobieren ]   │
└───────────────────────────────────────────────────────────────────────┘
```

- Wortmarke „Who2Be" links, Textlogo (keine Grafik — Markenentwicklung ist out
  of scope), verlinkt auf `/`.
- Navigation: **Funktionen** (Ankerlink `#funktionen`), **Selbst betreiben**
  (`/selbst-hosten`), **Dokumentation** (`{{DOCS_URL}}`, öffnet neuen Tab),
  **Preise** (`/preise`).
- Rechts ein Knopf: **Kostenlos ausprobieren** → `{{APP_URL}}`.
- „Dokumentation" steht in der Hauptnavigation, nicht im Footer — sie ist der
  einzige messbelegte Ersatz für Sozialbeweis.
- Die Kopfzeile bleibt beim Scrollen **nicht** kleben. Begründung: sie kostet
  auf 320 px ein Fünftel der Höhe und die Seite ist kurz genug.
- Unter `md` (< 768 px): Navigation in ein aufklappbares Menü, der Knopf
  bleibt sichtbar. Details in `gestaltung-und-zustaende.md` §4.
- Barrierefreiheit: erster fokussierbarer Inhalt ist ein Sprunglink
  **„Zum Inhalt springen"**, sichtbar bei Fokus.

---

## 1 · Hauptaussage (Hero)

**Zweck:** In drei Sekunden klären, was das Ding tut und warum es nicht das
nächste Glücksspiel ist.
**Bündel:** A in der Überschrift, B im Satz darunter.
**Einwand:** „Noch ein Agenten-Baukasten, der mir Wunder versprechen will."

```
┌───────────────────────────────────────────────────────────────────────┐
│                                                                       │
│   AGENTENKONFIGURATION                                                │
│                                                                       │
│   Routineaufgaben abgeben, ohne bei jedem Lauf                        │
│   zu hoffen, dass es klappt.                                          │
│                                                                       │
│   Who2Be verwaltet Personas, Abläufe und Wissen deiner Agenten        │
│   als versionierte Dokumente mit Freigabe und Verlauf. Was ein        │
│   Agent tut, steht damit fest — statt vom Zufall des Modells          │
│   abzuhängen.                                                         │
│                                                                       │
│   [ Kostenlos ausprobieren ]   [ Selbst betreiben ]                   │
│                                                                       │
│   Ohne Kreditkarte. Anmeldung mit Google oder GitHub.                 │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

**Texte:**

- Eyebrow: `AGENTENKONFIGURATION`
- H1: **Routineaufgaben abgeben, ohne bei jedem Lauf zu hoffen, dass es klappt.**
- Fließtext: **Who2Be verwaltet Personas, Abläufe und Wissen deiner Agenten
  als versionierte Dokumente mit Freigabe und Verlauf. Was ein Agent tut, steht
  damit fest — statt vom Zufall des Modells abzuhängen.**
- Knopf 1 (primär): **Kostenlos ausprobieren** → `{{APP_URL}}`
- Knopf 2 (sekundär): **Selbst betreiben** → `/selbst-hosten`
- Kleingedrucktes darunter: **Ohne Kreditkarte. Anmeldung mit Google oder
  GitHub.**

**Warum diese Formulierung:**

- „ohne bei jedem Lauf zu hoffen, dass es klappt" ist die Owner-Vorgabe „nicht
  auf die Wahrscheinlichkeit der Modelle vertrauen" in Alltagssprache — im
  ersten Satz, wie gefordert, aber als *Bedingung* am Ziel statt als
  Methodenwerbung.
- „statt vom Zufall des Modells abzuhängen" wiederholt den Gedanken einmal
  präzise für die, die genauer lesen.
- Kein „Kontrolle", kein „Zuverlässigkeit", kein „KI-gestützt", keine
  Superlative — n8n besetzt den Kontroll-Wortlaut, und Marketing-Sprache ist
  gegen diese Zielgruppe messbar schädlich (Nielsen 1997).
- Der Hinweis auf Google/GitHub steht **hier**, nicht erst beim Klick: die
  Karte verlangt die ehrliche Ankündigung der Provider-Anmeldung.
- Nur **ein** primärer Knopf pro Fläche
  (`docs/frontend/design-language.md:52-53`), der zweite ist `outline`.

**Zustände:** Rein statisch, kein Bild, kein Video im ersten Bildschirm — der
erste sichtbare Inhalt darf nicht auf eine Ladeanfrage warten.

---

## 2 · Das Problem in drei Sätzen

**Zweck:** Der Zielgruppe zeigen, dass hier jemand ihr Problem kennt, statt es
wegzuversprechen.
**Bündel:** A.
**Einwand:** „Mein Problem ist nicht, dass ich keinen Agenten bauen kann —
mein Problem ist, dass er nicht verlässlich arbeitet."

```
┌───────────────────────────────────────────────────────────────────────┐
│  Das Problem ist nicht der erste Lauf, sondern der fünfzigste.        │
│                                                                       │
│  Ein Agent aufzusetzen dauert eine Stunde. Ihn über Monate gleich     │
│  arbeiten zu lassen, ist die eigentliche Arbeit: der Prompt liegt in  │
│  einem Chatverlauf, der Ablauf in einem Kopf, das Firmenwissen in     │
│  drei Dokumenten mit unterschiedlichem Stand. Wenn dann etwas         │
│  schiefgeht, weiß niemand, was sich geändert hat.                     │
│                                                                       │
│  Genau diese Dinge behandelt Who2Be wie Code: versioniert,            │
│  freigegeben, vergleichbar.                                           │
└───────────────────────────────────────────────────────────────────────┘
```

**Texte:**

- H2: **Das Problem ist nicht der erste Lauf, sondern der fünfzigste.**
- Absatz: **Ein Agent aufzusetzen dauert eine Stunde. Ihn über Monate gleich
  arbeiten zu lassen, ist die eigentliche Arbeit: der Prompt liegt in einem
  Chatverlauf, der Ablauf in einem Kopf, das Firmenwissen in drei Dokumenten
  mit unterschiedlichem Stand. Wenn dann etwas schiefgeht, weiß niemand, was
  sich geändert hat.**
- Abschluss-Satz, visuell hervorgehoben: **Genau diese Dinge behandelt Who2Be
  wie Code: versioniert, freigegeben, vergleichbar.**

**Warum:** Der Bericht empfiehlt, das Fast-Richtig-Problem zu benennen statt es
wegzuversprechen (66 % nennen „almost right, but not quite" als Hauptfrust).
Die Formulierung nennt das Problem ohne die fremde Studienzahl zu zitieren —
Zahlen auf einer Startseite sind nicht prüfbar und wirken wie Marketing.

---

## 3 · Was Who2Be ist

**Zweck:** Die Kategorie klären. Ohne diesen Abschnitt raten Besucher, ob es
ein Chatbot, ein Workflow-Werkzeug oder eine Datenbank ist.
**Bündel:** A + B.
**Einwand:** „Was genau ist das — und was ersetzt es bei mir?"

```
┌───────────────────────────────────────────────────────────────────────┐
│  Eine Stelle, an der die Konfiguration deiner Agenten liegt.          │
│                                                                       │
│  Who2Be ist keine Agenten-Laufzeit und ersetzt nicht dein             │
│  Werkzeug zum Ausführen. Es ist die Stelle, an der die                │
│  Konfiguration liegt und aus der sich deine Agenten zur Laufzeit      │
│  bedienen — über einen MCP-Server, mit 83 Werkzeugen zum Lesen,       │
│  Schreiben und Suchen.                                                │
│                                                                       │
│   ┌─────────────┐      ┌──────────────┐      ┌──────────────────┐     │
│   │  Who2Be     │ MCP  │  dein Agent  │      │  deine Aufgabe   │     │
│   │  Personas   │─────>│  Claude Code │─────>│  erledigt, jedes │     │
│   │  Playbooks  │      │  oder eigen  │      │  Mal gleich      │     │
│   │  Ressourcen │      │              │      │                  │     │
│   └─────────────┘      └──────────────┘      └──────────────────┘     │
└───────────────────────────────────────────────────────────────────────┘
```

**Texte:**

- H2: **Eine Stelle, an der die Konfiguration deiner Agenten liegt.**
- Absatz: **Who2Be ist keine Agenten-Laufzeit und ersetzt nicht dein Werkzeug
  zum Ausführen. Es ist die Stelle, an der die Konfiguration liegt und aus der
  sich deine Agenten zur Laufzeit bedienen — über einen MCP-Server, mit
  83 Werkzeugen zum Lesen, Schreiben und Suchen.**
- Bildunterschrift zur Skizze: **Who2Be liefert Personas, Abläufe und Wissen
  an den Agenten aus. Was der Agent damit tut, bleibt deinem Werkzeug
  überlassen — angebunden über stdio oder als entfernte Verbindung mit
  OAuth, zum Beispiel an Claude Code oder Claude.ai.**

**Umsetzung der Skizze:** Inline-SVG oder reines HTML mit Kästen und Pfeilen —
**kein Rasterbild**. Begründung: scharf auf jedem Bildschirm, kein Ladegewicht,
Text bleibt vorlesbar. Das SVG braucht `role="img"` und ein
`<title>`/`aria-label` mit genau dem Text der Bildunterschrift.

**Ehrlichkeit an dieser Stelle ist Absicht:** „ersetzt nicht dein Werkzeug zum
Ausführen" verliert ein paar Besucher, die etwas anderes suchen — und spart
genau die Anmeldungen, die sofort wieder gehen.

---

## 4 · Der Ablauf in vier Schritten

**Zweck:** Den Mechanismus zeigen, der die Hero-Behauptung trägt. Das ist der
Winkel, der laut Recherche unbesetzt ist.
**Bündel:** B.
**Einwand:** „Wie greift das konkret in meine Arbeit?"

```
┌───────────────────────────────────────────────────────────────────────┐
│  Wie eine Änderung durchläuft                                         │
│                                                                       │
│  1 Entwurf      Du änderst eine Persona oder einen Ablauf.            │
│                 Die bisherige Version bleibt unangetastet aktiv.      │
│                                                                       │
│  2 Freigabe     Der Entwurf geht in die Prüfung. Ein Vergleich        │
│                 zeigt Zeile für Zeile, was sich geändert hat.         │
│                                                                       │
│  3 Aktiv        Nach der Freigabe liefert Who2Be die neue Version     │
│                 an die Agenten aus. Ab diesem Moment, nicht vorher.   │
│                                                                       │
│  4 Archiv       Die alte Version bleibt lesbar und lässt sich         │
│                 zurückholen. Auch in sechs Monaten.                   │
└───────────────────────────────────────────────────────────────────────┘
```

**Texte:**

- H2: **Wie eine Änderung durchläuft**
- Schritt 1, Titel **Entwurf**, Text: **Du änderst eine Persona oder einen
  Ablauf. Die bisherige Version bleibt unangetastet aktiv.**
- Schritt 2, Titel **Freigabe**, Text: **Der Entwurf geht in die Prüfung. Ein
  Vergleich zeigt Zeile für Zeile, was sich geändert hat.**
- Schritt 3, Titel **Aktiv**, Text: **Nach der Freigabe liefert Who2Be die neue
  Version an die Agenten aus. Ab diesem Moment, nicht vorher.**
- Schritt 4, Titel **Archiv**, Text: **Die alte Version bleibt lesbar und
  lässt sich zurückholen. Auch in sechs Monaten.**
- Satz unter der Liste: **Dieselben vier Zustände gelten für Personas,
  Abläufe, Wissensdokumente, Prompt-Bausteine und Werkzeug-Anbindungen.**

**Umsetzung:** geordnete Liste (`<ol>`), nicht vier Cards mit Icons — die
Reihenfolge ist die Information. Auf Mobilgeräten einspaltig untereinander,
ab `md` zweispaltig (2×2). Die Ziffern sind Listenzahlen, keine Grafiken.

**Belege:** `README.md:6-12`; `VersionDiffView.tsx`; MCP-`transition_*`- und
`restore_*`-Werkzeuge (`tool_requirements.py:157-198`).

---

## 5 · Was drin ist (Funktionsraster)

**Zweck:** Die Frage „reicht das für meinen Fall?" beantworten, ohne
Aufzählungswut.
**Bündel:** A (Aufgaben abgeben), B (Verlässlichkeit), C (Überblick — hier
zulässig, weil es *nicht* die Hauptbotschaft ist).
**Einwand:** „Kann es das, was ich brauche?"

Ankerziel `#funktionen`. Sechs Einträge, je Titel und zwei Sätze. Raster:
eine Spalte unter `sm`, zwei ab `sm`, drei ab `lg`.

**Texte:**

- H2: **Was Who2Be verwaltet**

1. **Personas** — **Identität, Ton, Grenzen und Arbeitsmodi eines Agenten,
   versioniert. Zwei Agenten können dieselbe Persona nutzen, ohne sie zu
   kopieren.**
2. **Abläufe (Playbooks)** — **Schritt-für-Schritt-Anweisungen mit
   Stichworten, die sie auslösen. Mehrere Abläufe lassen sich zu einem
   größeren zusammensetzen, statt sie abzuschreiben.**
3. **Wissensdokumente** — **Ressourcen im Blockeditor, mit Verweisen auf
   einzelne Blöcke und einer Rückwärtssuche: welcher Ablauf, welche Persona
   nutzt diesen Absatz?**
4. **Agenten** — **Ein Agent bündelt System-Prompt, erlaubte Werkzeuge und ein
   kuratiertes Langzeitgedächtnis. Welche Werkzeuge er überhaupt sieht, hängt
   an seinen Rechten.**
5. **Arbeitsbereich und Wissensbasis** — **Je Agent ein unversionierter
   Arbeitsbereich: Notizen, aufgenommene Dateien und Adressen, abfragbare
   Tabellen, Zeitverlauf. Was sich bewährt, wandert in einem ausdrücklichen
   Schritt in die kuratierten Ressourcen.**
6. **Suche** — **Volltext und sinnähnliche Suche über alle Inhalte, auch
   über Textstellen innerhalb langer Dokumente.**

Unter dem Raster ein Satz mit Link: **Die vollständige Liste der 83
MCP-Werkzeuge und der Architektur steht in der Dokumentation.** → `{{DOCS_URL}}`

**Bewusst nicht im Raster:** Mehrbenutzer-Rollen, zweiter Faktor,
Einladungen — die gehören zu Abschnitt 8 (Entscheider-Stoff), nicht zur
Produktneugier. Und: kein Eintrag „KI-Funktionen".

---

## 6 · Zwei Wege

**Zweck:** Die Autonomie-Frage klären, bevor sie zum Absprunggrund wird.
**Bündel:** A (der schnelle Weg) + D (der prüfbare Weg).
**Einwand:** „Muss ich meine Prompts und mein Firmenwissen zu einem fremden
Anbieter hochladen?"

Zwei nebeneinanderliegende Flächen (unter `md` untereinander).

**Texte:**

- H2: **Selbst betreiben oder in der Cloud — dieselbe Software**

**Linke Fläche, Titel: Selbst betreiben**
- **Docker ist die einzige Voraussetzung. Kein Python, kein Node, keine
  Konfigurationsdatei.**
- Codeblock, wortgleich aus `README.md:62-63`:
  ```
  git clone https://github.com/luetzey/who2be.git && cd who2be
  docker compose up -d --wait
  ```
- **Danach läuft alles auf deinem Rechner: Datenbank, Weboberfläche,
  MCP-Server. Kein Konto bei uns, keine Daten bei uns.**
- Link: **Anleitung und Betrieb auf einem Server** → `/selbst-hosten`

**Rechte Fläche, Titel: Cloud**
- **Wir betreiben es, du meldest dich an und legst los. Für den Anfang
  kostenlos, ohne Kreditkarte.**
- **Anmeldung mit Google oder GitHub — ein Passwortformular gibt es nicht.**
- Knopf (`outline`, nicht primär — der primäre Knopf der Seite sitzt im
  Hero und im Abschluss): **Kostenlos ausprobieren** → `{{APP_URL}}`
- Link: **Was Free und Pro umfassen** → `/preise`

Satz unter beiden Flächen: **Beide Wege nutzen denselben Quellcode. Die Lizenz
erlaubt den internen Gebrauch kostenlos und wird zwei Jahre nach jeder
Veröffentlichung zu Apache 2.0.**

**Belege:** `README.md:57-64`, `README.md:171-178`,
`OAuthButtons.tsx:35,73,83`.

**Der Codeblock ist Absicht:** er ist gleichzeitig der Weg zum Ergebnis ohne
Konto (Login-Wall-Entschärfung, NN/g) und ein prüfbarer Beweis statt eines
Versprechens. Er braucht einen „Kopieren"-Knopf mit `aria-label="Befehle
kopieren"` und Rückmeldung **Kopiert** im Text des Knopfes; ohne JavaScript
bleibt der Block markierbar.

---

## 7 · Was beim ersten Klick passiert

**Zweck:** Den Bruch verhindern, den die Karte benennt — Provider-Anmeldung als
Überraschung.
**Bündel:** A.
**Einwand:** „Werde ich gleich zur Kasse gebeten oder in ein Formular
gezwungen?"

Schmaler Abschnitt, drei Zeilen, kein Kasten-Design, ruhig gesetzt.

**Texte:**

- H2: **Was beim Ausprobieren passiert**
- Liste (drei Punkte):
  1. **Du wirst mit Google oder GitHub angemeldet. Ein Passwort legst du nicht
     an — es gibt kein Passwortformular.**
  2. **Vor der Anmeldung bestätigst du einmal die Nutzungsbedingungen und die
     Datenschutzerklärung. Eine E-Mail-Adresse musst du nicht zusätzlich
     angeben, und eine Kreditkarte ebenfalls nicht.**
  3. **Danach landest du in einem eigenen Arbeitsbereich und kannst die erste
     Persona anlegen.**
- Abschlusszeile: **Lieber ohne Konto? Dann nimm den Weg über Docker — er
  führt zur selben Oberfläche auf deinem Rechner.** → Link `/selbst-hosten`

**Belege:** `SignupPage.tsx:28-36,189-253` (die Zustimmungs-Checkbox schaltet
auch die Provider-Knöpfe frei — deshalb steht sie hier und nicht im
Kleingedruckten), `OAuthButtons.tsx:35`.

**Variante für später, nicht jetzt einsetzen:** Sobald Apple als Provider in
GoTrue konfiguriert und in `OAuthButtons.tsx` verdrahtet ist, lautet Punkt 1:
**„Du wirst mit Google, GitHub oder Apple angemeldet. Ein Passwort legst du
nicht an — es gibt kein Passwortformular."** Gleiches gilt für die Zeilen in
Abschnitt 1 und 6. Bis dahin wäre die Nennung von Apple falsch.

---

## 8 · Für die Leute, die es freigeben müssen

**Zweck:** Weiterschickbares Material. In 52 % der Fälle dient ein Agent
internen Mitarbeitern — es gibt also meist jemanden, dem der Einsatz erklärt
werden muss (Bericht §1.3 Bündel D).
**Bündel:** D.
**Einwand:** „Was sage ich der IT, dem Datenschutz, meinem Chef?"

Wichtig: Dieser Abschnitt ist **keine Rollen-Tür**. Er fragt niemanden, wer er
ist, sondern ist nach Aufgabe benannt („freigeben"). Damit erfüllt er die
NN/g-Bedingung „Prioritize topics and tasks over audience categories".

**Texte:**

- H2: **Wenn jemand anderes zustimmen muss**
- Einleitung: **Die Angaben, nach denen in einer Freigabe meistens gefragt
  wird — zum Nachlesen und Weiterschicken.**
- Vier Punkte:
  1. **Wo die Daten liegen.** **Selbst betrieben: auf deiner Maschine. In der
     Cloud: auf Servern in Deutschland oder Finnland. Details und die Liste der
     beteiligten Dienstleister stehen in der Datenschutzerklärung.**
  2. **Quellcode und Lizenz.** **Der Quellcode ist einsehbar. Lizenz ist die
     Functional Source License 1.1 mit Apache-2.0-Zukunft: intern frei nutzbar,
     kein Wiederverkauf als Konkurrenzangebot, und zwei Jahre nach jeder
     Veröffentlichung gilt Apache 2.0.**
  3. **Rollen und Zugriff.** **Organisationen und Arbeitsbereiche, Rollen
     Admin, Editor und Viewer. Einladungen laufen über einen Link per
     E-Mail, sensible Schritte verlangen einen zweiten Faktor.**
  4. **Nachvollziehbarkeit.** **Jede Änderung an Personas, Abläufen und
     Wissensdokumenten erzeugt eine neue Version mit Freigabestand. Zugriffe
     von Agenten werden protokolliert.**
- Drei Links am Ende: **Quellcode ansehen** → `{{REPO_URL}}` ·
  **Architektur und Entscheidungen** → `{{DOCS_URL}}` ·
  **Selbst betreiben** → `/selbst-hosten`

**Belege:** `README.md:35-36` (Rollen, Einladungen, zweiter Faktor),
`README.md:171-178` (Lizenz), `deploy/hetzner/README.md` (Betrieb),
`docs/compliance/agent-access-log.md` (Zugriffsprotokoll),
`docs/cloud-hosting-owner-guide.md` §6 (Standort).

**Nicht hier hin:** Zertifizierungsbehauptungen, SLA-Zusagen, „DSGVO-konform"
als Siegel. Siehe `README.md` §3.1.

---

## 9 · Ehrliche Lage

**Zweck:** Das Sozialbeweis-Problem lösen, ohne etwas zu erfinden.
**Bündel:** A, B, D gleichzeitig.
**Einwand:** „Wer nutzt das überhaupt? Wieso soll ich dem trauen?"

Ein Abschnitt, ruhig gesetzt, nicht als Warnkasten — sonst wird aus einer
Tatsachenangabe eine Entschuldigung.

**Texte:**

- H2: **Wo Who2Be gerade steht**
- Absatz: **Who2Be ist neu. Es gibt keine Kundenlogos, die ich zeigen kann,
  und keine Nutzerzahl, die etwas beweisen würde. Was es stattdessen gibt,
  lässt sich in zehn Minuten selbst prüfen:**
- Drei Punkte:
  - **Der Quellcode ist einsehbar** — mitsamt der Architekturentscheidungen und
    ihrer Begründung. → `{{REPO_URL}}`
  - **Die Dokumentation ist vollständig und nicht hinter einer Anmeldung** —
    Installation, Betrieb, Schnittstelle, Sicherheitsangaben. → `{{DOCS_URL}}`
  - **Es läuft ohne mich** — ein Befehl auf deinem Rechner, und du kannst
    beurteilen, ob es hilft. → `/selbst-hosten`
- Schlusssatz: **Wenn es nicht passt, hast du eine halbe Stunde verloren und
  kein Abo.**

**Warum keine Zahlen, keine Sterne, kein „Beta":** Das Wort „Beta" lädt zu
einem Qualitätsurteil ein, das die Seite nicht belegen kann, und
GitHub-Sterne veralten in jede Richtung. Die drei Punkte sind
**prüfbare Behauptungen** — das ist die Stanford-Empfehlung „Make it easy to
verify the accuracy of the information".

---

## 10 · Preise kurz

**Zweck:** Preistransparenz auf der Startseite, Details auf `/preise`.
**Bündel:** A.
**Einwand:** „Was kostet es wirklich, und was ist die Falle?"

**Texte:**

- H2: **Was es kostet**
- Zwei Zeilen im Vergleich:
  - **Selbst betreiben — 0 €. Intern frei nutzbar, kein Konto, keine Grenze
    durch uns.**
  - **Cloud — Free ab 0 €, Pro 29 € im Monat. Monatlich kündbar, ohne
    Kreditkarte zum Anfangen.**
- Link: **Alle Grenzen im Vergleich** → `/preise`

Keine Preistabelle auf der Startseite — die vollständigen Zahlen stehen einmal
und nur einmal auf `/preise`, damit sie nicht an zwei Stellen veralten.

---

## 11 · Häufige Fragen

**Zweck:** Die restlichen Einwände knapp abräumen, ohne die Seite zu
verlängern.
**Bündel:** gemischt.

Umsetzung: `<details>`/`<summary>`-Paare, erstes Element **offen**. Funktioniert
ohne JavaScript, ist von Tastatur bedienbar und von Screenreadern lesbar.

- H2: **Häufige Fragen**

1. **Brauche ich Who2Be, wenn ich schon ein Werkzeug zum Bauen von Agenten
   nutze?**
   **Vermutlich ergänzend, nicht statt. Who2Be führt keine Agenten aus — es
   hält ihre Konfiguration fest und liefert sie zur Laufzeit über MCP aus.
   Dein Ausführungswerkzeug bleibt, wo es ist.**
2. **Welche Modelle werden unterstützt?**
   **Who2Be spricht selbst mit keinem Modell. Es liefert Personas, Abläufe und
   Wissen an deinen Agenten; welches Modell der benutzt, entscheidest du in
   deinem Werkzeug.**
3. **Wie binde ich es an Claude Code an?**
   **Über MCP: entweder als lokale Verbindung oder als entfernte Verbindung
   mit OAuth. In der Oberfläche erzeugst du unter Einstellungen einen Token
   und kopierst die fertige Client-Konfiguration daneben.**
4. **Kann ich später von der Cloud auf den eigenen Server wechseln?**
   **Es ist dieselbe Software. Für den Umzug der Inhalte gibt es heute keinen
   Knopf „alles exportieren" — die Inhalte liegen in einer Postgres-Datenbank
   und lassen sich mit den üblichen Datenbankwerkzeugen sichern und
   einspielen. Ein Ausfuhr-Knopf in der Oberfläche steht auf der Liste.**
5. **Gibt es eine englische Fassung?**
   **Die Oberfläche ja, Deutsch und Englisch. Diese Website ist vorerst nur
   deutsch.**
6. **Ich habe einen Fehler gefunden oder einen Wunsch.**
   **Ins öffentliche Verzeichnis auf GitHub damit — dort landen Fehler und
   Wünsche und werden beantwortet.** → `{{REPO_URL}}/issues`

**Belege:** Frage 3: `README.md:85-101`. Frage 4: kein Export-Endpunkt im Repo
auffindbar — deshalb die ehrliche Antwort statt eines Versprechens; die
Datenhaltung steht in `README.md:51`. Frage 5: `apps/web/src/i18n/locales/`.

---

## 12 · Abschluss-Aufforderung

**Zweck:** Letzter Anker für die, die bis unten gelesen haben.
**Bündel:** A.

```
┌───────────────────────────────────────────────────────────────────────┐
│           Nimm dir eine Aufgabe, die du zu oft selbst machst.         │
│                                                                       │
│                    [ Kostenlos ausprobieren ]                         │
│                                                                       │
│    Ohne Kreditkarte, Anmeldung mit Google oder GitHub — oder mit      │
│    Docker auf dem eigenen Rechner.                                    │
└───────────────────────────────────────────────────────────────────────┘
```

- H2: **Nimm dir eine Aufgabe, die du zu oft selbst machst.**
- Knopf (primär): **Kostenlos ausprobieren** → `{{APP_URL}}`
- Zeile darunter: **Ohne Kreditkarte, Anmeldung mit Google oder GitHub — oder
  mit Docker auf dem eigenen Rechner.** (Wort „Docker" verlinkt auf
  `/selbst-hosten`.)

---

## 13 · Fußzeile

Drei Spalten ab `md`, gestapelt darunter.

- Spalte **Produkt**: Funktionen (`#funktionen`) · Preise (`/preise`) ·
  Selbst betreiben (`/selbst-hosten`)
- Spalte **Technik**: Dokumentation (`{{DOCS_URL}}`) · Quellcode
  (`{{REPO_URL}}`) · Änderungen (`{{REPO_URL}}/blob/main/CHANGELOG.md`) ·
  Fehler melden (`{{REPO_URL}}/issues`)
- Spalte **Rechtliches**: Impressum (`/impressum`) · Datenschutz
  (`/datenschutz`) · Nutzungsbedingungen (`{{APP_URL}}/legal/terms`) ·
  Auftragsverarbeitung (`{{APP_URL}}/legal/dpa`)
- Untere Zeile: **Who2Be · Lizenz FSL-1.1-Apache-2.0** (Wort „Lizenz" verlinkt
  auf `{{REPO_URL}}/blob/main/LICENSE`)

Kein „© 2026" — ein Jahr in der Fußzeile veraltet und ist rechtlich
entbehrlich. Externe Links tragen `rel="noopener"` und im
Barrierefreiheitsnamen den Zusatz „(externe Seite)".

---

## Seitentitel und Beschreibung

- `<title>`: **Who2Be — Agentenkonfiguration versioniert verwalten**
- `<meta name="description">`: **Personas, Abläufe und Wissen deiner
  KI-Agenten als versionierte Dokumente mit Freigabe und Verlauf. Selbst
  betreiben mit Docker oder kostenlos in der Cloud ausprobieren.**
- Open-Graph-Titel und -Beschreibung identisch. Ein Vorschaubild wird **nicht**
  spezifiziert (Markenentwicklung out of scope) — ohne Bild rendern die
  Plattformen den Titel, das ist besser als ein improvisiertes Bild.

# Weitere Seiten, Navigation, Fußzeile, Rechtsseiten

> Teil der Website-Spezifikation, siehe [`README.md`](README.md).

## 1 · Navigation (alle Seiten gleich)

| Beschriftung | Ziel | Bemerkung |
|---|---|---|
| Who2Be (Wortmarke) | `/` | Textlogo, `font-semibold tracking-tight` |
| Funktionen | `/#funktionen` | auf der Startseite ein Ankersprung, auf anderen Seiten der volle Pfad |
| Selbst betreiben | `/selbst-hosten` | |
| Dokumentation | `{{DOCS_URL}}` | neuer Tab, Barrierefreiheitsname mit dem Zusatz „(externe Seite)" |
| Preise | `/preise` | |
| **Kostenlos ausprobieren** | `{{APP_URL}}` | Knopf, `variant=brand`, auf jeder Seite genau einmal in der Kopfzeile |

Die Kopfzeile enthält **keinen** Anmelde-Link neben dem Knopf. Begründung:
„Kostenlos ausprobieren" und „Anmelden" führen zum gleichen Ziel — zwei
Beschriftungen für denselben Weg stiften Zweifel, welcher der richtige ist. Wer
schon ein Konto hat, landet über denselben Knopf in der Anmeldung.

Aktive Seite ist mit `aria-current="page"` markiert und visuell durch
`text-foreground` statt `text-muted-foreground` (nicht durch Farbe allein —
`docs/frontend/design-language.md:479-480`).

## 2 · Fußzeile (alle Seiten gleich)

Inhalt und Aufbau stehen in [`startseite.md`](startseite.md) §13. Sie ist auf
allen fünf Seiten identisch.

## 3 · Seite „Selbst betreiben" `/selbst-hosten`

**Bündel:** A (Ergebnis ohne Hürde) und D (weiterschickbares Material).
**Entkräfteter Einwand:** „Ich will das nicht bei einem Fremden liegen haben"
und „Ich will es ansehen, ohne ein Konto anzulegen."

Diese Seite ist der Weg **ohne Anmeldung** und damit die Antwort auf die
Login-Wall. Sie steht in der Hauptnavigation, nicht im Footer.

### Aufbau und Texte

**Seitenkopf**
- Eyebrow: `SELBST BETREIBEN`
- H1: **Who2Be auf der eigenen Maschine**
- Einleitung: **Derselbe Quellcode, den wir in der Cloud betreiben. Docker ist
  die einzige Voraussetzung — kein Python, kein Node, keine
  Konfigurationsdatei.**

**Abschnitt „In zwei Befehlen"**
- H2: **In zwei Befehlen**
- Codeblock (wortgleich `README.md:62-63`):
  ```
  git clone https://github.com/luetzey/who2be.git && cd who2be
  docker compose up -d --wait
  ```
- Absatz: **Danach öffnest du `http://localhost:5173`, legst ein Konto an —
  lokal wird es ohne Mailversand sofort bestätigt — und landest in einem
  eigenen Arbeitsbereich.**
- Hinweis: **Der erste Start baut die Abbilder aus dem Quellcode und braucht ein
  paar Minuten. Wer stattdessen fertige Abbilder ziehen will, nimmt den zweiten
  Befehl aus der Anleitung im Verzeichnis.**
- Beleg: `README.md:57-83`.

**Abschnitt „Was dabei läuft"**
- H2: **Was dabei läuft**
- Absatz: **Der Stapel startet die Datenbank, die Anmeldung, die REST-Api, die
  Weboberfläche und den MCP-Server. Der MCP-Server hört auf
  `http://localhost:8765/mcp` und nimmt einen gewöhnlichen Who2Be-Token —
  eine OAuth-Einrichtung brauchst du dafür nicht.**
- Beleg: `README.md:85-98`.

**Abschnitt „Einen Agenten anbinden"**
- H2: **Einen Agenten anbinden**
- Absatz: **In der Oberfläche unter Einstellungen → Tokens erzeugst du einen
  Token und kopierst die fertige Client-Konfiguration, die daneben steht. Für
  Claude Code geht es auch von Hand:**
- Codeblock (nach `README.md:95-98`, Token bewusst maskiert):
  ```
  claude mcp add --transport http who2be http://localhost:8765/mcp \
    --header "Authorization: Bearer ***"
  ```
- Hinweis: **`***` ersetzt du durch deinen Token. Der Betrieb über stdio aus
  einem Quellcode-Auszug ist in der Dokumentation beschrieben.** → `{{DOCS_URL}}`

**Abschnitt „Von einem anderen Gerät"**
- H2: **Von einem anderen Gerät im Netz**
- Absatz: **Die Oberfläche spricht immer mit der Adresse, von der sie geladen
  wurde — eine Adresse im lokalen Netz funktioniert also ohne Neubau. Damit
  Anmeldung und Einladungslinks passen, setzt du beim Start dieselbe Adresse
  auch für das Backend:**
- Codeblock (`README.md:111`):
  ```
  WHO2BE_PUBLIC_URL=http://192.168.1.42:5173 docker compose up -d --wait
  ```
- Warnzeile: **Für den Betrieb außerhalb eines vertrauenswürdigen Netzes
  brauchst du den gehärteten Aufbau mit TLS. Der ist im Verzeichnis
  `deploy/hetzner/` beschrieben, mitsamt automatischem HTTPS, Backups und einem
  Betriebshandbuch.**
- Beleg: `README.md:103-116`, `deploy/hetzner/README.md`.

**Abschnitt „Auf einem Server"**
- H2: **Auf einem Server**
- Absatz: **Für den Dauerbetrieb gibt es einen fertigen Aufbau mit Docker
  Compose und Caddy: automatisches HTTPS, Sicherheits-Kopfzeilen,
  Backup-Dienst und ein Betriebshandbuch für Wiederherstellung und
  Schlüsseltausch. Wir betreiben unsere Cloud mit demselben Aufbau auf Servern
  in Deutschland oder Finnland.**
- Link: **Der Betriebsaufbau im Verzeichnis** →
  `{{REPO_URL}}/tree/main/deploy/hetzner`
- Beleg: `README.md:52,157-158`, `deploy/hetzner/README.md:348-362` (Standorte
  `nbg1`/`fsn1`/`hel1`).

**Abschnitt „Lizenz"**
- H2: **Was die Lizenz erlaubt**
- Absatz: **Who2Be steht unter der Functional Source License 1.1 mit
  Apache-2.0-Zukunft. Für den internen Gebrauch — auch in einem Unternehmen,
  auch kommerziell — ist die Nutzung frei. Nicht erlaubt ist, Who2Be als
  konkurrierendes Hosting-Angebot zu verkaufen. Jede Veröffentlichung wird
  zwei Jahre nach ihrem Erscheinen automatisch Apache 2.0.**
- Zusatz: **Wenn du eine darüber hinausgehende kommerzielle Lizenz brauchst,
  findest du die Kontaktadresse im Impressum.**
- Links: **Lizenztext** → `{{REPO_URL}}/blob/main/LICENSE` ·
  **Lizenzen der verwendeten Bibliotheken** →
  `{{REPO_URL}}/blob/main/THIRD-PARTY-LICENSES.md`
- Beleg: `README.md:171-178`.

**Abschnitt „Grenzen des eigenen Betriebs" — ehrlich, und deshalb wichtig**
- H2: **Was du dabei selbst übernimmst**
- Punkte:
  - **Updates, Backups und die Wiederherstellung im Fehlerfall.**
  - **Verschlüsselung des Datenbank-Datenträgers. Der Betriebsaufbau
    beschreibt, wie es geht, aber einrichten musst du es.**
  - **Erreichbarkeit. Es gibt keine Zusage von uns, weil es dein Server ist.**
- Beleg: `deploy/hetzner/README.md:350-356`.
- Abschlusszeile: **Wenn dir das zu viel ist, nimm die Cloud — dieselbe
  Software, wir kümmern uns darum.** → Link `/preise`

**Seitentitel**
- `<title>`: **Selbst betreiben — Who2Be**
- `<meta name="description">`: **Who2Be auf der eigenen Maschine: zwei Befehle,
  Docker als einzige Voraussetzung. Anbindung an MCP-Clients, Betrieb auf einem
  Server, Lizenzbedingungen.**

### Zustände dieser Seite

- Jeder Codeblock bekommt einen „Kopieren"-Knopf mit `aria-label="Befehl
  kopieren"`; nach dem Kopieren wechselt die Beschriftung für zwei Sekunden auf
  **Kopiert**. Ohne JavaScript bleibt der Text markierbar — der Knopf wird dann
  nicht gerendert (progressiv, kein toter Knopf).
- Codeblöcke scrollen waagerecht statt umzubrechen; der Scroll-Container hat
  `tabindex="0"` und ein `aria-label` mit dem Zweck des Blocks, damit er per
  Tastatur erreichbar ist.

## 4 · Impressum `/impressum` — was hineingehört

**Kein Rechtstext in dieser Spezifikation.** Diese Liste sagt, welche Angaben
der Owner liefern muss; die Formulierung gehört zum Betreiber bzw. zur
anwaltlichen Prüfung. Grundlage:
`docs/compliance/legal-texts-checklist.md:26-44` — dieselben Pflichtangaben wie
in der App, hier für den **Website-Betreiber** (identische Person, aber eine
eigene Seite, weil die Website ein eigener Telemediendienst ist).

| Pflichtangabe | Rechtsgrundlage | Was der Owner liefert |
|---|---|---|
| Name und Rechtsform | § 5 Abs. 1 Nr. 1 DDG | Vollständiger Name, bei einer Gesellschaft mit Rechtsform |
| Ladungsfähige Anschrift | § 5 Abs. 1 Nr. 1 DDG | Straße, Hausnummer, PLZ, Ort, Land. **Kein Postfach.** |
| Vertretungsberechtigte Person | § 5 Abs. 1 Nr. 1 DDG | Bei einer Gesellschaft die Geschäftsführung |
| E-Mail-Adresse | § 5 Abs. 1 Nr. 2 DDG | Pflicht |
| Telefonnummer | § 5 Abs. 1 Nr. 2 DDG | Nicht zwingend, aber empfohlen — sonst muss ein anderer schneller Kontaktweg da sein |
| Registereintrag | § 5 Abs. 1 Nr. 4 DDG | Registerart, Registergericht, Nummer — falls eingetragen |
| Umsatzsteuer-Identifikationsnummer | § 5 Abs. 1 Nr. 6 DDG, § 27a UStG | Falls vorhanden |
| Aufsichtsbehörde | § 5 Abs. 1 Nr. 3 DDG | Nur bei erlaubnispflichtiger Tätigkeit — hier voraussichtlich nicht einschlägig, der Owner bestätigt das |
| Verantwortlicher für den Inhalt | § 18 Abs. 2 MStV | Nur bei journalistisch-redaktionellen Inhalten. Eine Produktseite ohne Blog braucht es in der Regel nicht — Entscheidung des Owners |
| Hinweis zur Verbraucherschlichtung | § 36 VSBG | Aussage, ob eine Teilnahme besteht oder nicht. Der Hinweis auf die EU-Streitbeilegungsplattform ist nach deren Einstellung zu prüfen (`legal-texts-checklist.md:41-42`) |

Zusätzlich für die Website empfohlen, weil es Rückfragen erspart:
- Ein Satz, an welche Adresse Fehlerhinweise zur Website gehen (die
  Kontakt-Mail genügt).

**Struktur der Seite** (Überschriften vorgegeben, Inhalt vom Owner):
H1 **Impressum** · H2 **Anbieter** · H2 **Kontakt** · H2 **Registereintrag** ·
H2 **Umsatzsteuer** · H2 **Streitbeilegung**. Abschnitte ohne Inhalt werden
**weggelassen**, nicht mit „entfällt" gefüllt.

**Regel für den Bau:** Die Seite geht **nicht** mit Platzhaltern live. Fehlt
eine Angabe, bleibt die Website unveröffentlicht — ein Impressum mit
`<PLATZHALTER>` ist schlechter als keine Website.

## 5 · Datenschutzerklärung `/datenschutz` — was hineingehört

**Kein Rechtstext hier.** Und wichtig: Das ist die Erklärung für **die
Website**, nicht für die App. Die App hat ihre eigene unter
`{{APP_URL}}/legal/privacy` (`apps/web/src/features/legal/pages/PrivacyPage.tsx`).
Beide Texte dürfen sich nicht widersprechen; die Website-Erklärung ist die
kürzere, weil die Website weniger tut.

Was die Website tatsächlich verarbeitet — Grundlage für den Text:

| Vorgang | Was passiert | Was in den Text muss |
|---|---|---|
| Aufruf einer Seite | Der Webserver schreibt ein Zugriffsprotokoll | Welche Felder (IP-Adresse, Zeit, angeforderte Adresse, Statuscode, Referrer, Browserkennung), Zweck (Betrieb und Sicherheit), Rechtsgrundlage Art. 6 Abs. 1 lit. f DSGVO, **Speicherdauer** — die muss der Owner festlegen und im Server tatsächlich so einstellen |
| Hosting | Wo der Webserver steht | Anbieter, Standort, Bestehen eines Auftragsverarbeitungsvertrags. Quelle für die Cloud-Seite: `deploy/hetzner/README.md:357-362` (Hetzner, `nbg1`/`fsn1`/`hel1`) |
| Cookies | **Keine.** Die Website setzt keine Cookies und bindet keine Dritt-Inhalte ein | Eine klare Aussage „diese Website setzt keine Cookies und verwendet keine Analysewerkzeuge" — das ist die kürzeste und stimmigste Fassung. Wird dieser Zustand später geändert, muss der Text vorher geändert werden |
| Theme-Einstellung (hell/dunkel) | Falls umgesetzt, im lokalen Speicher des Browsers | Ein Satz: technisch notwendige Speicherung ohne Personenbezug, keine Übermittlung. Alternative: gar nicht speichern und der Systemeinstellung folgen — dann entfällt der Satz. **Empfehlung: der Systemeinstellung folgen** (siehe `gestaltung-und-zustaende.md` §2) |
| Ausgehende Links | Klicks führen zu GitHub und zur App | Hinweis, dass für verlinkte Angebote deren eigene Erklärungen gelten |
| Betroffenenrechte | — | Auskunft, Berichtigung, Löschung, Einschränkung, Widerspruch, Datenübertragbarkeit, Beschwerde bei der Aufsichtsbehörde; **die zuständige Aufsichtsbehörde muss namentlich benannt werden** (`legal-texts-checklist.md:63`) |
| Verantwortlicher | — | Name und Kontakt, deckungsgleich mit dem Impressum |

**Struktur der Seite** (Überschriften vorgegeben):
H1 **Datenschutzerklärung** · H2 **Verantwortlicher** · H2 **Zugriffsprotokolle
des Webservers** · H2 **Hosting** · H2 **Keine Cookies, keine
Analysewerkzeuge** · H2 **Links zu anderen Angeboten** · H2 **Deine Rechte** ·
H2 **Aufsichtsbehörde** · H2 **Stand dieser Erklärung**.

**Was der Owner außerdem entscheiden muss:**
- Speicherdauer der Zugriffsprotokolle (und sie im Server so einstellen).
- Ob ein Datenschutzbeauftragter benannt ist. Ist keiner benannt, gehört das
  nicht in den Text — die Nennung eines nicht existierenden DSB wäre falsch.
- Die zuständige Aufsichtsbehörde (hängt am Sitz).

**Trennung zur App, damit sich nichts widerspricht:** Die Website-Erklärung
sagt zur App **nur** einen Satz: **„Für die Nutzung der Anwendung selbst gilt
die dortige Datenschutzerklärung"**, mit Link. Anmeldung, Zahlungsabwicklung,
Mailversand und Auftragsverarbeiter der App gehören **nicht** in die
Website-Erklärung — sie stehen in `PrivacyPage.tsx` und werden dort gepflegt.

## 6 · Fehlerseite 404

Kein eigener Eintrag in der Seitenstruktur, aber notwendig.

- H1: **Diese Seite gibt es nicht.**
- Absatz: **Vielleicht ist die Adresse veraltet. Diese Wege führen weiter:**
- Drei Links: **Startseite** (`/`) · **Preise** (`/preise`) ·
  **Dokumentation** (`{{DOCS_URL}}`)
- Kein Witz, kein Maskottchen, keine Suchleiste (es gibt nichts zu durchsuchen).
- HTTP-Status **404**, nicht 200 mit Hinweistext.

## 7 · Adressen und Weiterleitungen

| Adresse | Verhalten |
|---|---|
| `/` | Startseite |
| `/preise` | Preisseite |
| `/selbst-hosten` | Selbst-Hosting |
| `/impressum` | Impressum |
| `/datenschutz` | Datenschutzerklärung |
| `/pricing`, `/preise/` | 301 auf `/preise` |
| `/self-hosting`, `/selfhosting` | 301 auf `/selbst-hosten` |
| `/imprint` | 301 auf `/impressum` |
| `/privacy` | 301 auf `/datenschutz` |
| `/docs`, `/dokumentation` | 302 auf `{{DOCS_URL}}` |
| `/app`, `/login`, `/anmelden` | 302 auf `{{APP_URL}}` |
| alles andere | 404 |

Die englischen Kurzformen kosten nichts und fangen geratene Adressen ab. Der
Pfadpräfix `/en/` bleibt frei für eine spätere englische Fassung.

Zusätzlich: `robots.txt` mit `Sitemap:`-Zeile, `sitemap.xml` mit den fünf
Seiten. Kein `noindex` — die Seite soll gefunden werden. SEO-Stichworte sind
out of scope; die Seitentitel und Beschreibungen in dieser Spezifikation sind
das, was gesetzt wird.

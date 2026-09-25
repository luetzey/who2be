# Preisseite `/preise`

> Teil der Website-Spezifikation, siehe [`README.md`](README.md).
> Alle Texte fertig. **Geschäftskritisch:** Mollie verlangt für die
> Verifizierung eine live erreichbare Seite mit sichtbaren Preisen.

## 1 · Zweck und Anspruch

- **Bündel A** (Ergebnis) und **Bündel D** (der, der es freigeben muss).
- **Entkräfteter Einwand:** „Was kostet es wirklich, und wo ist die Falle?"
- Preistransparenz ist laut TrustRadius vier Jahre in Folge der Wunsch Nr. 1 der
  Käufer und laut SlashData der dominante Ablehnungsgrund. Diese Seite ist
  deshalb kein Anhang, sondern der zweitwichtigste Inhalt der Website.
- Sie ist **ohne Anmeldung** erreichbar und in der Hauptnavigation verlinkt.

## 2 · Die echten Zahlen

Quellen, in dieser Rangfolge verbindlich:
`packages/billing/src/who2be_billing/plans.py:63-89` (Preis, MCP-Kontingent,
MCP-Rate) · `apps/api/src/who2be_api/licensing/entitlement.py:52,92-107`
(Element-Grenze) · `docs/licensing/plans.md:22-30` (Menschenlesbare
Einzelquelle) · `apps/web/src/features/billing/components/BillingPanel.tsx:39-42`
(dieselben Werte in der App).

| | Selbst betreiben | Free | Pro |
|---|---|---|---|
| Preis | 0 € | 0 € | 29 € im Monat |
| MCP-Anfragen im Monat | unbegrenzt | 1.000 | 100.000 |
| MCP-Anfragen in der Minute | unbegrenzt | 30 | 240 |
| Inhalts-Elemente je Arbeitsbereich | unbegrenzt | 50 | unbegrenzt |
| Betrieb | du | wir | wir |

**Sachlich wichtig, damit der Coder nichts erfindet:** Die Feature-Codes
`composite_playbooks`, `agents` und `audit_export` tauchen in der
Pro-Metadaten-Liste auf, werden aber **nirgends im Code als Zugangssperre
geprüft** (`docs/licensing/plans.md:32-43`). Sie sind deshalb **kein
Kaufargument** und stehen nicht auf der Seite. Wirksam sind ausschließlich
Preis, die beiden MCP-Grenzen und die Element-Grenze. Wer „Pro schaltet Agenten
frei" schreibt, behauptet eine Sperre, die nicht existiert.

**Ebenfalls nicht auf die Seite:** Speicherplatz. Es gibt im Repo keine
Speicher-Quota (`docs/cloud-hosting-owner-guide.md:38-44`) — also weder eine
Zusage noch eine nennbare Grenze. Die Seite schweigt dazu; die
Nutzungsbedingungen regeln es später.

## 3 · Aufbau

```
┌───────────────────────────────────────────────────────────────────────┐
│ Kopfzeile (wie Startseite)                                            │
├───────────────────────────────────────────────────────────────────────┤
│  Preise                                                               │
│  Drei Wege, dieselbe Software. Alle Grenzen stehen hier, nicht im     │
│  Kleingedruckten.                                                     │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ Selbst       │  │ Free         │  │ Pro          │                 │
│  │ betreiben    │  │              │  │ 29 € / Monat │                 │
│  │ 0 €          │  │ 0 €          │  │              │                 │
│  │ …            │  │ …            │  │ …            │                 │
│  │ [Anleitung]  │  │ [Kostenlos   │  │ [Kostenlos   │                 │
│  │              │  │  anfangen]   │  │  anfangen]   │                 │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                       │
│  Was die Zahlen bedeuten        (Tabelle, vollständig)                │
│  Was in allen Stufen gleich ist (Liste)                               │
│  Zahlung und Kündigung         (Liste)                                │
│  Fragen zum Preis               (details/summary)                     │
│  Abschluss-Aufforderung                                               │
├───────────────────────────────────────────────────────────────────────┤
│ Fußzeile (wie Startseite)                                             │
└───────────────────────────────────────────────────────────────────────┘
```

Reihenfolge der Stufen von links: **Selbst betreiben, Free, Pro.** Begründung:
Der kostenlose, konto-freie Weg steht zuerst, weil er die Login-Wall entschärft
und das einzige vollständig prüfbare Angebot ist. Pro steht rechts und ist
hervorgehoben (Rahmen in der Markenfarbe, kleines Textkennzeichen
**Empfohlen für laufenden Betrieb** — kein „Beliebteste Wahl", das wäre eine
erfundene Nutzungsbehauptung).

## 4 · Texte

### Seitenkopf

- Eyebrow: `PREISE`
- H1: **Preise**
- Einleitung: **Drei Wege, dieselbe Software. Alle Grenzen stehen hier, nicht im
  Kleingedruckten.**

### Umsatzsteuer-Hinweis — Owner entscheidet, Coder setzt eine Variante

Direkt unter der Einleitung, klein, `text-muted-foreground`. **Genau eine** der
beiden Zeilen wird gesetzt; welche, entscheidet der Owner (`README.md` §5,
Punkt 4):

- Variante A (Kleinunternehmerregelung, § 19 UStG):
  **Preis in Euro. Kein Umsatzsteuerausweis gemäß § 19 UStG.**
- Variante B (mit Umsatzsteuer):
  **Preis in Euro zuzüglich der gesetzlichen Umsatzsteuer.**

Der Coder setzt beide Zeilen als auskommentierte Alternative in die Textdatei
und aktiviert die vom Owner benannte. **Kein Platzhalter im gerenderten HTML.**

### Karte 1 — Selbst betreiben

- Titel: **Selbst betreiben**
- Preis: **0 €**
- Preiszusatz: **dauerhaft, auf deiner Maschine**
- Beschreibung: **Der vollständige Funktionsumfang auf deiner Hardware. Keine
  Anmeldung bei uns, keine Grenze durch uns.**
- Punkte:
  - **Alle Funktionen, keine Mengengrenzen von uns**
  - **Deine Daten bleiben auf deinen Systemen**
  - **Docker ist die einzige Voraussetzung**
  - **Intern frei nutzbar (Lizenz FSL-1.1-Apache-2.0)**
  - **Betrieb, Backups und Updates machst du**
- Knopf (`outline`): **Zur Anleitung** → `/selbst-hosten`

### Karte 2 — Free

- Titel: **Free**
- Preis: **0 €**
- Preiszusatz: **kein Abo, keine Kreditkarte**
- Beschreibung: **Zum Ausprobieren und für kleine Aufgaben. Ohne Zeitlimit.**
- Punkte:
  - **1.000 Agenten-Anfragen im Monat**
  - **30 Agenten-Anfragen in der Minute**
  - **Bis zu 50 Inhalts-Elemente je Arbeitsbereich**
  - **Alle Funktionen der Oberfläche**
  - **Wir betreiben es**
- Knopf (`outline`): **Kostenlos anfangen** → `{{APP_URL}}`

### Karte 3 — Pro (hervorgehoben)

- Kennzeichen: **Empfohlen für laufenden Betrieb**
- Titel: **Pro**
- Preis: **29 €**
- Preiszusatz: **im Monat, monatlich kündbar**
- Beschreibung: **Für Agenten, die täglich arbeiten.**
- Punkte:
  - **100.000 Agenten-Anfragen im Monat**
  - **240 Agenten-Anfragen in der Minute**
  - **Unbegrenzt viele Inhalts-Elemente**
  - **Alle Funktionen der Oberfläche**
  - **Wir betreiben es**
- Knopf (primär): **Kostenlos anfangen** → `{{APP_URL}}`
- Zeile unter dem Knopf: **Du fangst mit Free an und schaltest Pro später in
  den Einstellungen dazu.**

**Warum bei Pro kein Knopf „Pro kaufen":** Es gibt keinen Kaufweg von der
Website aus — der Checkout sitzt in der App unter den Abrechnungs-Einstellungen
(`apps/web/src/features/billing/components/BillingPanel.tsx`). Ein Knopf
„Kaufen", der auf eine Anmeldung führt, wäre genau die Überraschung, die
diese Seite vermeiden soll.

### Abschnitt „Was die Zahlen bedeuten"

- H2: **Was die Zahlen bedeuten**
- Absatz vor der Tabelle: **Gezählt werden die Zugriffe deiner Agenten auf
  Who2Be — nicht deine Klicks in der Oberfläche. Ein Agent, der einmal am Tag
  eine Persona und zwei Abläufe liest, verbraucht rund 90 Anfragen im Monat.**
- Tabelle, vollständig, mit Zeilenköpfen links:

  | | Selbst betreiben | Free | Pro |
  |---|---|---|---|
  | **Preis** | 0 € | 0 € | 29 € im Monat |
  | **Agenten-Anfragen im Monat** | unbegrenzt | 1.000 | 100.000 |
  | **Agenten-Anfragen in der Minute** | unbegrenzt | 30 | 240 |
  | **Inhalts-Elemente je Arbeitsbereich** | unbegrenzt | 50 | unbegrenzt |
  | **Betrieb, Backup, Updates** | du | wir | wir |
  | **Wo die Daten liegen** | bei dir | Deutschland oder Finnland | Deutschland oder Finnland |

- Satz unter der Tabelle: **Inhalts-Elemente sind Personas, Abläufe,
  Wissensdokumente, Agenten, Prompt-Bausteine und Werkzeug-Anbindungen — alles,
  was du als eigenes Dokument anlegst.**
- Rechenbeispiel als Herleitung der 90 Anfragen (damit die Zahl nicht wie eine
  Behauptung wirkt): **Gerechnet mit 30 Tagen und drei Lesezugriffen am Tag.
  Wie viele Anfragen dein Fall tatsächlich braucht, siehst du in der App unter
  den Abrechnungs-Einstellungen — dort läuft ein Zähler mit.**

### Abschnitt „Was in allen Stufen gleich ist"

- H2: **Was in allen Stufen gleich ist**
- Absatz: **Es gibt keine Funktion, die wir hinter dem Preis wegschließen. Der
  Unterschied zwischen Free und Pro sind Mengen, nicht Fähigkeiten.**
- Punkte:
  - **Versionen mit Freigabestand, Vergleich und Zurückholen**
  - **Personas, Abläufe, Wissensdokumente, Agenten, Prompt-Bausteine,
    Werkzeug-Anbindungen**
  - **Arbeitsbereich je Agent samt Wissensbasis**
  - **Volltext- und sinnähnliche Suche**
  - **MCP-Server mit 83 Werkzeugen, über stdio oder als entfernte Verbindung**
  - **Mehrere Personen, Rollen Admin, Editor und Viewer, Einladungen per Link**

**Beleg dafür, dass dieser Satz stimmt:** `docs/licensing/plans.md:32-43` —
nur `core` und die daraus abgeleitete Element-Grenze sind wirksam, die übrigen
Feature-Codes gaten nichts.

### Abschnitt „Zahlung und Kündigung"

- H2: **Zahlung und Kündigung**
- Punkte:
  - **Bezahlt wird monatlich über unseren Zahlungsdienstleister Mollie. Die
    Zahlungsdaten liegen dort, nicht bei uns.**
  - **Die Buchung läuft in der App unter Einstellungen → Abrechnung. Du
    brauchst dafür ein Konto und die Rolle Admin.**
  - **Kündigung jederzeit zum Ende des laufenden Monats.**
  - **Nach einer Kündigung fällt die Organisation auf Free zurück — deine
    Inhalte bleiben lesbar. Gesperrt wird nichts.**
  - **Liegt die Zahl deiner Inhalts-Elemente dann über der Free-Grenze,
    kannst du weiterhin alles lesen, aber erst wieder Neues anlegen, wenn du
    unter 50 Elementen bist.**

**Belege:** `docs/licensing/plans.md:47-50` (Rückfall auf Free, keine Sperre),
`apps/api/src/who2be_api/licensing/entitlement.py:92-107` (Element-Grenze wirkt
über das aufgelöste Entitlement). Die letzte Zeile ist die ehrliche
Konsequenz der Code-Logik und gehört auf die Seite, weil sie sonst als
unangenehme Überraschung auftritt.

### Abschnitt „Fragen zum Preis"

`<details>`/`<summary>`, erstes offen.

- H2: **Fragen zum Preis**

1. **Brauche ich eine Kreditkarte, um anzufangen?**
   **Nein. Free verlangt kein Zahlungsmittel und läuft nicht ab.**
2. **Wird Free nach 14 Tagen zu Pro?**
   **Nein. Free ist eine eigene Stufe, kein Testzeitraum. Es passiert nichts
   automatisch.**
3. **Was passiert, wenn ich das Monatskontingent ausschöpfe?**
   **Die Zugriffe deiner Agenten werden abgelehnt, bis der Monat wechselt oder
   du Pro buchst. Die Oberfläche funktioniert weiter — betroffen sind nur die
   Agenten-Zugriffe.**
4. **Bekomme ich eine Rechnung?**
   **Über die Zahlungsbestätigung von Mollie ja. Ein eigenes Rechnungsdokument
   mit fortlaufender Nummer stellen wir heute nicht automatisch aus — wenn du
   eines brauchst, schreib uns an die Adresse im Impressum.**
5. **Gibt es Rabatte für ein Jahr im Voraus?**
   **Nein, es gibt nur die monatliche Zahlung.**
6. **Und wenn ich mehr brauche als Pro?**
   **Dann ist der eigene Betrieb der günstigere Weg — dort setzen wir keine
   Grenzen. Für eine kommerzielle Lizenz außerhalb des internen Gebrauchs
   findest du die Kontaktadresse im Impressum.**

**Belege:** Frage 3: `docs/licensing/plans.md:22-30` (Quoten wirken auf die
MCP-Zugriffe, nicht auf die Oberfläche). Frage 4: **ehrliche Antwort** — es
gibt kein Rechnungs-Artefakt im Repo
(`docs/cloud-hosting-owner-guide.md:390-396`). Frage 5: nur ein Intervall
`"1 month"` in `plans.py:78`. Frage 6: `README.md:177-178`.

### Abschluss

- H2: **Fang mit Free an.**
- Absatz: **Du brauchst keine Entscheidung für Pro, um zu sehen, ob Who2Be
  hilft.**
- Knopf (primär): **Kostenlos anfangen** → `{{APP_URL}}`
- Zeile: **Oder mit Docker auf dem eigenen Rechner.** → `/selbst-hosten`

## 5 · Pflege — wo die Zahlen herkommen

Die Zahlen stehen an **einer** Stelle im Website-Quellcode (eine
Datenstruktur, aus der Karten und Tabelle gerendert werden), nicht doppelt in
Karte und Tabelle. Ein Kommentar darüber nennt die Repo-Quellen:

```
// Quelle der Wahrheit, in dieser Reihenfolge:
//   packages/billing/src/who2be_billing/plans.py  (Preis, MCP-Quoten)
//   apps/api/src/who2be_api/licensing/entitlement.py  (FREE_ENTITY_QUOTA)
//   docs/licensing/plans.md  (menschenlesbare Einzelquelle)
// Änderung dort => diese Datei nachziehen.
```

## 6 · Seitentitel

- `<title>`: **Preise — Who2Be**
- `<meta name="description">`: **Selbst betreiben kostenlos, Free ab 0 €, Pro
  29 € im Monat. Alle Mengengrenzen im Vergleich, ohne Anmeldung.**

## 7 · Zustände

- Die Seite ist statisch. Kein Währungs- oder Intervall-Umschalter (es gibt nur
  Euro und nur den Monat) — ein Umschalter mit einer Option ist eine leere
  Bedienung.
- Die drei Karten sind ein `<ul>` mit drei `<li>`, damit Screenreader die Anzahl
  ansagen. Preis als `<p>` mit sichtbarem Text „29 €" und einem
  `<span class="sr-only">` „im Monat", falls das Intervall visuell nur klein
  daneben steht.
- Die Tabelle nutzt `<th scope="row">` und `<th scope="col">`, damit die
  Zuordnung in Screenreadern erhalten bleibt. Unter `md` scrollt sie waagerecht
  in einem Container mit `tabindex="0"` und `aria-label="Preisvergleich,
  waagerecht scrollbar"` — kein Umbau zu Kartenstapeln, weil dabei die
  Vergleichbarkeit verloren geht.
- Weitere Zustandsvorgaben in `gestaltung-und-zustaende.md`.

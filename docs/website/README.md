# Website-Spezifikation Who2Be — Index, Seitenstruktur, Belege

> Stand: 2026-09-25 · Autor: Designer-Rolle (Kanban `t_90ca6959`) · Grundlage:
> Recherchebericht `website-motivationstypen-2026-09-25.md` (Karte `t_72d665c2`)
> und der Repo-Stand dieses Worktrees.
>
> **Geltungsbereich:** die öffentliche Marketing-Website (eigene statische
> Seite, getrennt vom App-Code). **Nicht** die App-UI unter `apps/web/`.

## Dateien dieser Spezifikation

| Datei | Inhalt |
|---|---|
| `README.md` (diese Datei) | Seitenstruktur, Begründung je Seite, Produktwahrheits-Belegtabelle, offene Owner-Angaben |
| [`startseite.md`](startseite.md) | Startseite Abschnitt für Abschnitt, alle Texte fertig |
| [`preise.md`](preise.md) | Preisseite, echte Limits, Mollie-Verifizierungsanforderung |
| [`weitere-seiten.md`](weitere-seiten.md) | Selbst-Hosting, Doku-Weiterleitung, Rechtsseiten, 404, Navigation, Footer |
| [`gestaltung-und-zustaende.md`](gestaltung-und-zustaende.md) | Designsprache, Responsive, Tastatur, Kontraste, Lade-/Fehlerzustände, Performance |

Alle sichtbaren Texte stehen in diesen Dateien **fertig formuliert** mit
Volltext-Umlauten. Der Coder übernimmt sie wortgleich; Kürzungen oder
Umformulierungen gehen zurück an den Designer.

---

## 1 · Die drei Entscheidungen, die diese Spezifikation trägt

### 1.1 Reihenfolge der Botschaft: Ziel oben, Mechanismus direkt darunter

Die Karte verlangt den Differenzierungssatz („nicht auf die Wahrscheinlichkeit
der Modelle vertrauen") „weit nach oben". Der Recherchebericht widerspricht in
der Reihenfolge: belegtes Hauptmotiv ist Produktivität (80 %) bzw. weniger
Arbeitsstunden (72 %), Risikominderung nennen nur 12 % als Motiv
(MAP-Studie, arXiv:2512.04123v3).

**Entscheidung: beides, in einem Atemzug — Ziel in der H1, Mechanismus im
direkt folgenden Satz, beide im ersten Bildschirm.**

Begründung: Die Owner-Vorgabe „weit nach oben" ist erfüllt, wenn der Satz im
ersten sichtbaren Block steht — sie verlangt nicht, dass er das erste Wort ist.
Der Bericht belegt, dass das *Ziel* verkauft und die *Kontrolle* erklärt,
warum das Ziel hält. Die H1 nennt darum die Routine, der Subheadline-Satz
nennt in einem Nebensatz die Verlässlichkeit. Ein Besucher liest beide
zusammen in unter drei Sekunden.

Abweichung gegenüber dem Bericht: Wir setzen den Kontrollsatz **höher** als
er empfiehlt (nicht „darunter" als eigener Abschnitt, sondern direkt in die
Subheadline), weil die Owner-Vorgabe gesetzt ist und der Bericht seine
Reihenfolgeempfehlung selbst nur als Ableitung ausweist.

### 1.2 Der Winkel: Konfiguration wie Code, nicht „Kontrolle"

n8n besetzt „Build AI agents you can actually follow / Inspect every decision"
wörtlich, dazu on-prem, air-gapped, Audit-Logs, RBAC (Bericht §4.1). Frontal
dagegen zu spielen heißt, mit dem Argument des Stärkeren gegen ihn zu
spielen.

**Entscheidung: Die Seite verkauft nicht „Kontrolle", sondern die konkrete
Mechanik — Agentenkonfiguration als versioniertes, review-pflichtiges
Artefakt** (Draft → Review → Active → Archived, mit Diff und Rückverfolgung).
Das ist laut Bericht §4.4 auf keiner der 16 geprüften Wettbewerber-Startseiten
zu finden und im Repo vollständig belegt (Belegtabelle §3).

Konsequenz für die Texte: keine Vokabeln wie „volle Kontrolle",
„Zuverlässigkeit garantiert", „Governance". Stattdessen Verben und
Zustandsnamen, die im Produkt existieren: *versionieren, freigeben,
vergleichen, zurückholen*.

### 1.3 Sozialbeweis: Dokumentation, Quellcode, Selbst-Hosting, ehrliche Neuheit

Es gibt keine Kundenlogos, keine Testimonials, keine Nutzerzahlen — und keine
werden erfunden. Der einzige messbelegte Ersatz ist **Dokumentation** (npm-
Studie, 118 Entwickler + 2.527 Pakete, JSS 2023: wichtigster Einzelfaktor,
93 %; Regression bestätigt die README-Größe als eigenen Erklärungsfaktor).

**Entscheidung — vier Beweisformen, in dieser Rangfolge:**

1. **Dokumentation prominent, nicht im Footer** (Hauptnavigation, plus eigener
   Abschnitt auf der Startseite). Belegt wirksam.
2. **Quellcode und Lizenz sichtbar** — Repo-Link, FSL-1.1-Apache-2.0 mit dem
   Zwei-Jahres-Übergang nach Apache 2.0 benannt. Prüfbares Signal, kein
   Versprechen.
3. **Selbst-Hosting mit einem Befehl** — `docker compose up -d --wait`,
   nachprüfbar, ohne Konto. Deckt gleichzeitig den belegt einflussreichsten
   Kaufauslöser ab, den ein Solo-Entwickler herstellen kann (Ausprobieren).
4. **Ehrliche „gerade neu"-Ansage** in einem eigenen kurzen Abschnitt
   (`startseite.md` §9). Kein Selbstmitleid, kein „Beta-Disclaimer" —
   eine Tatsachenangabe plus die drei Dinge, die man stattdessen prüfen kann.

Bewusst **nicht** verwendet: GitHub-Sterne-Zahl (wäre heute ein schwaches
Signal und veraltet sofort), Roadmap-Prozentzahlen, „vertrauen uns bereits",
Produktivitätszahlen jeder Art (METR 2025 misst −19 %, METR hat 2026 die
Nachfolgemessung selbst als unzuverlässig zurückgezogen — die Beleglage
erlaubt keine Produktivitätsaussage).

---

## 2 · Seitenstruktur zum Start

Fünf Seiten. Jede zusätzliche Seite kostet Pflege, und der Owner ist allein.

| # | Seite | Pfad | Pflicht? | Begründung |
|---|---|---|---|---|
| 1 | Startseite | `/` | gesetzt | Einstieg, Hauptbotschaft, alle vier Beweisformen |
| 2 | Preise | `/preise` | gesetzt | Mollie verlangt für die Verifizierung eine live erreichbare Seite mit sichtbaren Preisen. Zusätzlich: Preistransparenz ist vier Jahre in Folge Wunsch Nr. 1 der Käufer (TrustRadius) und Preis der dominante Ablehnungsgrund (SlashData). |
| 3 | Selbst-Hosting | `/selbst-hosten` | ja (begründet) | Trägt zwei Dinge, die keine andere Seite trägt: den Weg **ohne Konto** (Login-Wall-Entschärfung, NN/g) und das weiterschickbare Material für den Entscheider hinter dem Nutzer (Lizenz, Betriebsform, Datenhaltung). Ohne diese Seite müsste die Startseite beides tragen und würde zu lang. |
| 4 | Impressum | `/impressum` | gesetzt | § 5 DDG |
| 5 | Datenschutzerklärung | `/datenschutz` | gesetzt | DSGVO Art. 13/14 |

**Bewusst nicht zum Start:**

| Nicht gebaut | Warum nicht |
|---|---|
| Dokumentations-Seite auf der Website | Die Doku liegt im Repo (`README.md`, `docs/`) und ist dort gepflegt. Eine zweite Kopie auf der Website ist die klassische Doppelquelle, die veraltet. Die Website **verlinkt** sie prominent (Hauptnavigation „Dokumentation" → Repo-URL, `target="_blank"`, mit Hinweis „öffnet GitHub"). Der belegte Faktor ist die Erreichbarkeit der Doku, nicht ihr Wohnort. |
| Changelog-Seite | Es gibt `CHANGELOG.md` im Repo und GitHub-Releases. Die Wirkung eines Changelogs als Vertrauensersatz ist laut Bericht §5.3 **unbelegt**. Footer-Link genügt. |
| Blog | Keine Inhalte, kein Autor, kein Zeitbudget. Ein leerer Blog mit zwei alten Beiträgen ist ein Negativsignal. |
| Vergleichsseite gegen n8n/CrewAI | Frontal gegen den Stärkeren mit dessen Argument (Bericht §4.1). Außerdem Pflegelast bei jeder fremden Produktänderung. |
| AGB und AVV/DPA als Website-Seiten | Existieren bereits in der App (`apps/web/src/features/legal/pages/TermsPage.tsx`, `DpaPage.tsx`) und gelten für das Vertragsverhältnis, das erst in der App entsteht. Die Website verlinkt sie im Footer auf die App-Pfade. Keine zweite Textquelle. |
| Kontaktformular | Ein Formular ohne Betreuung ist ein Versprechen ohne Deckung. Statt dessen die Kontakt-Mail im Impressum und der Repo-Issue-Tracker im Footer. |
| Sprachumschalter / englische Fassung | Website zum Start **nur deutsch** (`<html lang="de">`). Die App ist zweisprachig (`apps/web/src/i18n/locales/{de,en}.json`), die Website ist es nicht — eine zweite Sprachfassung verdoppelt die Textpflege bei einem Owner allein. Der Coder legt die Struktur i18n-fähig an (Texte in einer Datei je Sprache, Pfadpräfix `/en/` reserviert, aber nicht ausgeliefert), damit die Erweiterung später kein Umbau ist. |

Eine Folgekarte für „Dokumentations-Landingpage auf der Website" ist
vertretbar, sobald die Repo-Doku über GitHub hinaus gepflegt werden soll —
heute nicht.

---

## 3 · Produktwahrheit: jede Funktionsbehauptung mit Belegstelle

Der Coder darf **keine** Funktionsaussage auf die Seite bringen, die nicht in
dieser Tabelle steht. Neue Aussagen brauchen einen neuen Tabelleneintrag mit
Dateiverweis.

| Aussage auf der Website | Belegstelle im Repo |
|---|---|
| Personas, Playbooks, Ressourcen und Agenten sind versioniert und tragen einen Status Draft → Review → Active → Archived | `README.md:6-12`; `apps/web/src/components/data/StatusBadge.tsx`; `packages/models/src/who2be_models/tool_requirements.py:174-192` (`transition_persona`, `transition_playbook`, `transition_resource`, `transition_external_tool`, `transition_system_prompt`) |
| Änderungen lassen sich als Unterschied zweier Versionen ansehen | `apps/web/src/components/version/VersionDiffView.tsx`; `apps/web/src/lib/lineDiff.ts`; MCP-Werkzeug `diff_versions` (`tool_requirements.py:153`) |
| Alte Versionen lassen sich zurückholen | MCP-Werkzeuge `restore_persona`, `restore_playbook`, `restore_resource`, `restore_external_tool`, `restore_system_prompt` (`tool_requirements.py:157,161,166,188,198`) |
| Personas beschreiben Identität, Ton, Grenzen und Modi eines Agenten | `README.md:16-17`; `apps/web/src/features/personas/pages/` |
| Playbooks sind Schritt-für-Schritt-Abläufe mit Auslöse-Stichworten und lassen sich zu Bündeln zusammensetzen | `README.md:18-19` (ADR-0024); MCP `list_triggers`, `set_playbook_composes` (`tool_requirements.py:130,163`) |
| Ressourcen sind Wissensdokumente mit Blockeditor, Blockverweisen und Rückwärtssuche | `README.md:20-21` (ADR-0022); MCP `list_resource_blocks`, `find_usages` (`tool_requirements.py:134,150`) |
| Agenten bündeln System-Prompt, Werkzeug-Regeln und ein kuratiertes Langzeitgedächtnis | `README.md:22-23` (ADR-0044); `apps/web/src/features/agents/pages/AgentDetailPage.tsx` |
| Jeder Agent hat einen unversionierten Arbeitsbereich: Notizen, Datei- und URL-Aufnahme, abfragbare Tabellen, Zeitverlauf | `README.md:24-27` (ADR-0047–0049); `apps/web/src/features/workarea/pages/` |
| Wissensbasis mit typisierten Kanten und Belegbezug; die Übernahme in kuratierte Ressourcen ist ein eigener Schritt | `README.md:24-27`; MCP `search_kb`, `create_node`, `create_edge`, `neighbors`, `promote_artifact` (`tool_requirements.py:230-239`) |
| Wiederverwendbare System-Prompt-Bausteine und Anbindung externer Werkzeuge über Platzhalter | `README.md:28-30` (ADR-0040, ADR-0043); `apps/web/src/features/system-prompts/`, `apps/web/src/features/tools/` |
| Volltextsuche und semantische Suche über die Inhalte | `README.md:31-32` (ADR-0046); MCP `search`, `search_content` (`tool_requirements.py:144,149`) |
| Agenten greifen zur Laufzeit über einen MCP-Server zu — **83 Werkzeuge** | `packages/models/src/who2be_models/tool_requirements.py:123-257` (83 Einträge); der Drift-Test `apps/mcp/tests/test_policy_filter.py:300-305` erzwingt Gleichheit zwischen registrierten Werkzeugen und dieser Liste. **Achtung:** `README.md:31` nennt 81 — veraltet, siehe §5 offene Punkte. |
| Anbindung über stdio oder als entfernter Connector mit OAuth 2.1, z. B. an Claude Code oder Claude.ai | `README.md:33-34` (ADR-0036); `README.md:85-101`; `apps/web/src/features/auth/pages/OAuthConsentPage.tsx` |
| Welche Werkzeuge ein Agent sieht, hängt an seinen Rechten | `README.md` (ADR-0042); `apps/mcp/tests/test_policy_filter.py` |
| Organisationen und Arbeitsbereiche, Rollen Admin/Editor/Viewer, Einladungen per Magic-Link, zweiter Faktor für sensible Schritte | `README.md:35-36` (ADR-0023); `apps/web/src/features/settings/pages/MembersPage.tsx`; `docs/mfa-admin.md` |
| Selbst betreiben: Docker ist die einzige Voraussetzung, ein Befehl startet den Stapel | `README.md:57-64` |
| Zugriff von anderen Geräten im Netz ohne Neubau | `README.md:103-112` |
| Produktionsbetrieb mit Docker Compose und Caddy, automatisches HTTPS, Backup-Runbook | `README.md:52`, `README.md:157-158`; `deploy/hetzner/README.md` |
| Die Cloud läuft auf Servern in Deutschland oder Finnland | `deploy/hetzner/README.md:357-362` (Hetzner-Regionen `nbg1`/`fsn1` in DE, `hel1` in FI, alle EU/EWR) |
| Zugriffe von Agenten werden protokolliert | `docs/compliance/agent-access-log.md`; MCP-Werkzeug-Protokollierung `apps/mcp/tests/test_tool_logging.py` |
| Lizenz FSL-1.1-Apache-2.0: für internen Gebrauch frei, kein Konkurrenz-Hosting, jede Veröffentlichung wird zwei Jahre später Apache 2.0 | `README.md:171-178`; `LICENSE` |
| Anmeldung in der Cloud über Google oder GitHub | `apps/web/src/features/auth/components/OAuthButtons.tsx:35,73,83`; Texte `apps/web/src/i18n/locales/de.json:732-735` |
| Vor der Anmeldung ist die Zustimmung zu AGB und Datenschutzerklärung nötig | `apps/web/src/features/auth/pages/SignupPage.tsx:28-36,189-253` (Consent-Checkbox gated auch die Provider-Buttons) |
| Free: 1.000 MCP-Anfragen/Monat, 30/Minute, 50 Inhalts-Elemente je Arbeitsbereich | `packages/billing/src/who2be_billing/plans.py:63-71`; `apps/api/src/who2be_api/licensing/entitlement.py:52,92-107`; `docs/licensing/plans.md:22-30` |
| Pro: 29 €/Monat, 100.000 MCP-Anfragen/Monat, 240/Minute, unbegrenzte Inhalts-Elemente | `packages/billing/src/who2be_billing/plans.py:74-89`; `docs/licensing/plans.md:22-30`; `apps/web/src/features/billing/components/BillingPanel.tsx:39-42` |
| Kündigung oder ausbleibende Zahlung fällt auf Free zurück, nicht in eine Sperre | `docs/licensing/plans.md:47-50` |

### 3.1 Was ausdrücklich **nicht** behauptet werden darf

| Nicht behaupten | Grund |
|---|---|
| „Anmeldung mit Apple" | Im Code existieren nur Google und GitHub (`OAuthButtons.tsx:35`). Die Owner-Vorgabe nennt Apple; solange kein Apple-Provider konfiguriert ist, wäre der Satz falsch. Umgang: siehe `startseite.md` §7 (der Textbaustein nennt Google und GitHub; eine fertige Variante mit Apple liegt daneben und wird erst eingesetzt, wenn der Provider live ist). |
| Zeit- oder Produktivitätsgewinne in Zahlen („30 % schneller", „spart x Stunden") | Keine Messung im Repo, und die externe Beleglage trägt es nicht (METR 2025 −19 %, METR 2026 Selbstrücknahme). |
| „Rechnung wird automatisch erstellt" / „Umsatzsteuer wird abgeführt" | Es gibt kein Rechnungs-Artefakt im Repo (`docs/cloud-hosting-owner-guide.md:390-399`). |
| Speicherplatz-Zusagen („unbegrenzter Speicher", „x GB inklusive") | Es gibt im Repo keine Speicher-Quota (`docs/cloud-hosting-owner-guide.md:38-44`) — also weder eine Zusage noch eine Grenze, die man nennen könnte. Die Preisseite schweigt zu Speicher. |
| Verfügbarkeits- oder Reaktionszusagen (SLA) | SLA-Werte sind offen (`docs/compliance/legal-texts-checklist.md:82-83`). |
| „ISO-zertifiziert", „DSGVO-konform" als Siegel | Es gibt ein C5-Mapping und eine VVT als Arbeitsdokumente (`docs/compliance/`), keine Zertifizierung. Zulässig ist nur die Tatsachenangabe, wo die Daten liegen und dass ein AVV-Gerüst existiert. |
| Nutzerzahlen, Kundennamen, Bewertungen, „beliebt bei" | Existieren nicht. |
| Konkrete Preisangabe für eine Enterprise-Lizenz | Im Repo steht nur „für eine kommerzielle Enterprise-Lizenz: Kontakt" (`README.md:177-178`), kein Preis. |

---

## 4 · Technische Rahmenbedingungen für den Bau

Astro oder 11ty entscheidet die Baukarte. Für den Inhalt gilt unabhängig davon:

- **Ziel-Adressen als Build-Konfiguration, nicht als Text im Markup.** Der
  Coder legt drei Umgebungsvariablen an und nutzt sie an jeder Stelle, an der
  diese Spezifikation `{{APP_URL}}`, `{{REPO_URL}}` oder `{{DOCS_URL}}`
  schreibt:

  | Variable | Bedeutung | Vorbelegung |
  |---|---|---|
  | `PUBLIC_APP_URL` | Einsprungpunkt in die Cloud-App (Registrierung/Anmeldung) | vom Owner zu setzen; ohne Wert bricht der Build ab (kein stiller Link ins Leere) |
  | `PUBLIC_REPO_URL` | Quellcode | `https://github.com/luetzey/who2be` (`README.md:62`) |
  | `PUBLIC_DOCS_URL` | Dokumentationseinstieg | `https://github.com/luetzey/who2be#readme` |

  Diese drei Platzhalter sind **Konfiguration**, kein Textplatzhalter — in
  keinem sichtbaren Satz steht eine Lücke.
- **Kein Web-Font-Download.** Die Website übernimmt den System-Font-Stack der
  App (`docs/frontend/design-language.md:100-109`), Begründung in
  `gestaltung-und-zustaende.md` §1.
- **Kein Analytics, kein Tracker, keine eingebetteten Drittinhalte** (keine
  YouTube-Einbettung, keine Schriftart von einem CDN). Folge: die Website
  braucht **kein Cookie-Banner**. Das ist eine bewusste Entscheidung mit
  drei Wirkungen: keine Einwilligung nötig (§ 25 TDDDG), kein
  Glaubwürdigkeitsverlust durch Overlay, schnelle Ladezeit. Wer später
  Statistik will, nimmt ein serverseitiges Log-Auswertungsverfahren ohne
  Personenbezug und ändert die Datenschutzerklärung — nicht umgekehrt.
- **Statisches HTML ohne Laufzeit-JavaScript-Pflicht.** Jeder Inhalt und jeder
  Link funktioniert ohne JavaScript. JavaScript ist nur für das
  Mobil-Navigationsmenü und den Theme-Umschalter erlaubt, beide mit
  funktionierendem Fallback (`gestaltung-und-zustaende.md` §5).
- **Keine Formulare.** Die Website nimmt keine Eingaben an — kein Newsletter,
  kein Kontaktformular, kein Mail-Feld. Damit existiert auf der Website keine
  Verarbeitung außer Server-Logs.

---

## 5 · Was der Owner liefern muss, bevor die Seite live geht

Ohne diese Angaben ist die Seite baubar, aber nicht veröffentlichungsreif.

| # | Angabe | Wofür | Quelle/Vorlage |
|---|---|---|---|
| 1 | Domain der Website und `PUBLIC_APP_URL` | Links, Impressum, Mollie-Verifizierung | — |
| 2 | Impressumsangaben vollständig | § 5 DDG | Pflichtliste in `weitere-seiten.md` §4, abgeleitet aus `docs/compliance/legal-texts-checklist.md:26-44` |
| 3 | Datenschutzangaben für die **Website** (nicht die App) | DSGVO Art. 13 | Pflichtliste in `weitere-seiten.md` §5 |
| 4 | Entscheidung Umsatzsteuer-Ausweis beim Preis | Preisangabenverordnung / § 19 UStG | `preise.md` §4 — zwei fertige Textvarianten, Owner kreuzt eine an |
| 5 | Bestätigung, dass die Cloud-Registrierung offen ist (`WHO2BE_LAUNCH_MODE` **nicht** `coming_soon`) | Sonst zeigt die App nach dem Klick auf „Kostenlos ausprobieren" eine „Wir arbeiten noch"-Seite — der Bruch, den die Karte ausdrücklich vermeiden will | `docs/signup-and-invites.md:14-24` |
| 6 | Bestätigung, dass Google **und** GitHub als Provider in GoTrue konfiguriert sind | Der Text auf der Startseite nennt beide namentlich | `apps/web/src/features/auth/components/OAuthButtons.tsx:35` |

**Offener Repo-Widerspruch, den diese Spezifikation nicht selbst behebt:**
`README.md:31` nennt 81 MCP-Werkzeuge, die durchgesetzte Registry hat 83
(`tool_requirements.py:123-257`, abgesichert durch den Drift-Test in
`apps/mcp/tests/test_policy_filter.py:300-305`). Die Website nimmt **83**, weil
die Registry die durchgesetzte Quelle ist. Die README-Zahl gehört nachgezogen
— dafür ist eine eigene Karte angelegt (siehe Übergabe dieser Karte), weil
das eine Code-/Doku-Änderung ist und keine Designarbeit.

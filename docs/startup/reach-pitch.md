# Who2Be — Pitch-Dossier (REACH / Förder-Bewerbung)

> Arbeitsdokument für die Bewerbung beim REACH EUREGIO Start-up Center und
> anschließende Förderungen (z. B. EXIST). Die produktbezogenen Punkte sind aus
> dem Code belegt; persönliche Angaben sind mit **[BITTE ERGÄNZEN]** markiert.
> Stand: 2026-07-12.

---

## Kurzfassung (Elevator Pitch)

**Who2Be ist die versionierte Konfigurationsdatenbank für KI-Agenten — eine
Single Source of Truth, aus der beliebige LLM-Clients (Claude, ChatGPT & Co.)
per offenem Standard-Protokoll ihre Persona, ihre Playbooks und ihr Wissen
ziehen.** Statt Agenten-Prompts als lose Textschnipsel in Notion, Google Docs
oder verstreut im Code zu pflegen, verwalten Teams sie bei Who2Be zentral,
versioniert und rechtegesteuert — mit vollständigem Änderungsverlauf und einem
Freigabe-Workflow wie in der Software-Entwicklung.

Kurzformel: **„Git + CMS für die Persönlichkeit und das Playbook von
KI-Agenten."**

---

## 1. Problem — Wen nervt was, und wie löst man es heute (schlecht)?

Wer ernsthaft mit KI-Agenten arbeitet (LLM-gestützte Assistenten, Copiloten,
Automatisierungen), steht vor einem wachsenden Konfigurations-Chaos:

- **Der „Charakter" und das „Handbuch" eines Agenten sind heute verstreut.**
  System-Prompt, Verhaltensregeln, wiederkehrende Arbeitsanweisungen
  („Playbooks") und Hintergrundwissen liegen als Copy-&-Paste-Text in Notion,
  Google Docs, Confluence, in Chat-Verläufen oder hartkodiert im Code.
- **Keine Versionierung, keine Nachvollziehbarkeit.** Ändert jemand einen
  Prompt, ist der alte Stand weg. Es gibt kein „Wer hat wann was warum
  geändert?", kein Zurückrollen, keinen Review vor der Freigabe. Bei einem
  Werkzeug, das direkt das Verhalten eines Agenten steuert, ist das riskant.
- **Kein geregelter Freigabe-Prozess.** Ein experimenteller Prompt und ein
  produktiv genutzter Prompt sehen gleich aus. Es fehlt der Status-Übergang
  *Entwurf → Review → Aktiv → Inaktiv*, den man aus der Software-Auslieferung
  kennt.
- **Mehrfachpflege statt Wiederverwendung.** Dieselbe „So schreibst du eine
  Zusammenfassung"-Anweisung wird in fünf Agenten kopiert. Ändert sich die
  Regel, muss man fünf Stellen anfassen — und vergisst welche.
- **Kein Team-Zugriffsmodell.** Wer darf einen produktiven Agenten-Prompt
  ändern? Heute: jeder mit Doc-Zugriff. Rollen, Mandanten, Audit — Fehlanzeige.
- **Bruch zwischen „Pflege" und „Nutzung".** Der Ort, an dem man den Prompt
  *pflegt* (Notion), ist nicht der Ort, an dem der Agent ihn *lädt*. Man
  kopiert manuell hin und her — die Quelle driftet vom Live-Stand ab.

**Der heutige „Workaround" ist also: Prompt-Engineering per Textdokument** —
unversioniert, ohne Rollen, ohne Freigabe, doppelt gepflegt und vom Live-System
entkoppelt. Das skaliert nicht über ein paar Bastel-Agenten hinaus.

---

## 2. Lösung — Was wird konkret gebaut?

**Who2Be ist eine lauffähige, selbst-hostbare Softwareplattform** (kein Konzept,
kein Mockup) mit drei Zugängen zur selben zentralen Datenbasis:

1. **Web-Oberfläche** (React/TypeScript) — zum Pflegen und Freigeben:
   Personas, Playbooks, Ressourcen (Wissen) und zusammengesetzte Workflows
   („Composites") anlegen, bearbeiten, versionieren und über einen
   Status-Workflow (*draft → review → active → inactive*) freigeben. Inklusive
   Dashboard, Änderungs-Historie, Diff-Ansicht zwischen Versionen, Rückverweisen
   („welcher Agent nutzt dieses Playbook?") und einem Editor für strukturiertes
   Wissen.

2. **REST-API** (FastAPI) — die einzige Quelle der Wahrheit und der einzige
   Datenbank-Eigentümer. Klar geschichtet (Router → Service → Repository),
   jede Änderung erzeugt automatisch eine unveränderliche Versions-Momentaufnahme.

3. **MCP-Server** (Model Context Protocol) — die entscheidende Zutat: Über den
   **offenen MCP-Standard** kann sich jeder kompatible KI-Client (Claude,
   ChatGPT u. a.) direkt mit Who2Be verbinden und **zur Laufzeit** die aktive
   Persona, passende Playbooks und Ressourcen abrufen — inklusive
   Werkzeugen, mit denen der Agent selbst Inhalte anlegen, aktualisieren oder
   zur Freigabe einreichen kann. Angebunden per OAuth-2.1-Connector (ein Klick).

**Konkrete Fähigkeiten, die bereits im Code stehen:**

- **Versionierung** über separate History-Tabellen: jeder Speichervorgang =
  unveränderlicher Snapshot; Zurückrollen auf ältere Stände möglich.
- **Status-/Freigabe-Workflow** pro Version (Entwurf, Review, Aktiv, Inaktiv).
- **Mandantenfähigkeit**: `Organisation → Workspace → Inhalte`, mit
  **Rollen-System** (admin > editor > viewer) und Einladungen per Magic-Link.
- **Composite-Playbooks**: Playbooks aus Sub-Playbooks orchestrieren (beliebige
  Tiefe, Zyklus-Schutz) — wiederverwendbare Bausteine statt Copy-Paste.
- **Applied vs. Triggered**: ein Playbook wird entweder fest in den Prompt
  eingebettet oder erst bei einem Stichwort-Treffer nachgeladen (Token-sparend).
- **Feedback-Flywheel**: Agenten melden zurück, welches Playbook sie genutzt
  haben und was veraltet ist — die Bibliothek verbessert sich im Betrieb.
- **Suche** über Namen und Inhalte, **Discovery-Tools**, **Audit-Logs**,
  **Rate-Limits**, **MFA-Login**, **feingranulare Agenten-Schreibrechte**.
- **Zwei Editionen aus einer Codebasis**: On-Prem (selbst gehostet) und Cloud
  (mit optionalem Billing) — Build-zeit-isoliert, sodass das On-Prem-Artefakt
  den Billing-Code physisch nicht enthält.

**Produkt-Fokus (bewusste Abgrenzung):** Who2Be *speichert und liefert*
Agenten-Kontext, es *führt* keine Agenten aus. Kein Chat-Host, keine
LLM-Laufzeitumgebung, kein allgemeines Wiki/CMS. Und: **modellneutral** — keine
Bindung an einen einzigen LLM-Anbieter.

---

## 3. Zielgruppe / Kunde — Wer zahlt am Ende?

**Primär B2B.** Zahlende Kunden sind Organisationen, die mehr als nur einen
Bastel-Agenten betreiben und für die Agenten-Verhalten ein pflegebedürftiges,
geschäftskritisches Asset wird:

- **KI-/Software-Teams und Agenturen**, die für sich oder für Kunden Agenten
  bauen und deren Prompts/Playbooks professionell versionieren und freigeben
  müssen (statt in Docs zu verwalten).
- **Unternehmen mit mehreren internen KI-Assistenten** (Support, Vertrieb,
  interne Tools), die eine zentrale, rollengesteuerte Quelle der Wahrheit für
  Agenten-Konfiguration brauchen — mit Audit-Trail und Freigabe-Prozess.
- **Regulierte/On-Prem-affine Organisationen**, die aus Datenschutz- oder
  Compliance-Gründen selbst hosten müssen — genau dafür ist die
  selbst-hostbare Edition gebaut (DSGVO-/Compliance-Bausteine sind angelegt:
  Verfahrensdoku, VVT, Datenlöschung, C5-Mapping).

**Käufer-Rolle:** Engineering-Lead / Head of AI / Plattform-Team (führt es ein),
Budget aus dem Team- oder Tooling-Etat.

**Warum zahlungsbereit:** Der Schmerz wächst mit der Zahl der Agenten. Ab dem
Punkt, an dem Agenten-Konfiguration Team-Arbeit, geschäftskritisch und
auditpflichtig wird, ist „Prompt in Notion" nicht mehr tragbar — und eine
dedizierte, versionierte, self-hostbare Lösung wird ihr Geld wert.

**Nicht die Zielgruppe (vorerst):** einzelne Endverbraucher / B2C-Hobby-Nutzer.
Der Wert entsteht bei Teams und Mehrfach-Agenten-Betrieb.

---

## 4. Was daran neu ist — Warum gibt es das so noch nicht?

- **MCP-first statt Anbieter-Silo.** Who2Be setzt konsequent auf das Model
  Context Protocol (MCP) — den offenen Standard, über den moderne KI-Clients
  externen Kontext und Werkzeuge einbinden. Dadurch ist Who2Be **modellneutral**
  und nicht an das Prompt-/Assistant-System eines einzelnen Anbieters (OpenAI,
  Anthropic …) gekettet. Die meisten „Prompt-Management"-Angebote hängen an
  genau einer Plattform oder sind reine SaaS-Silos.
- **„Prompt-Verwaltung" gedacht wie Software-Auslieferung.** Versionierung mit
  unveränderlichen Snapshots, Freigabe-Status pro Version, Diffs, Rückverweise,
  Rollen/Review — das ist Engineering-Disziplin, angewandt auf Agenten-Kontext.
  Verbreitete Tools bleiben bei „Speicher deinen Prompt und probiere Varianten"
  stehen; sie behandeln den Prompt nicht als versioniertes, freigabepflichtiges
  Konfigurations-Artefakt mit Team-Zugriffsmodell.
- **Selbst-hostbar als Kern, nicht als Add-on.** Eine Codebasis, zwei
  Build-Profile; die On-Prem-Edition enthält den Cloud-/Billing-Code physisch
  nicht. Für datenschutzsensible Kunden ist echtes Self-Hosting ein
  Kauf-Kriterium — die meisten Wettbewerber sind Cloud-only.
- **Komposition + Feedback-Flywheel.** Wiederverwendbare, verschachtelbare
  Playbook-Bausteine (statt Copy-Paste) und ein Rückmelde-Kreislauf, in dem die
  Agenten selbst signalisieren, was genutzt wird und was veraltet ist. Die
  Bibliothek wird im Betrieb besser — nicht nur ein statischer Prompt-Speicher.
- **Der Agent als Mit-Autor.** Über die MCP-Schreib-Werkzeuge kann ein Agent
  neue Personas/Playbooks/Ressourcen selbst entwerfen und zur *Review*
  einreichen — das Freischalten bleibt aber hart gesperrt (Schutz vor
  Prompt-Injection). Diese Trennung „Agent darf vorschlagen, Mensch gibt frei"
  ist bewusst als Sicherheitsgrenze modelliert.

> **Ehrlicher Hinweis für die Bewerbung:** Der Neuheitswert liegt in der
> *Kombination* (MCP-nativ + versioniert + freigabegesteuert + self-hostbar +
> komponierbar), nicht in einem einzelnen patentierbaren Verfahren. Das ist für
> ein Software-Startup normal — aber ehrlich so benennen (siehe Punkt 5).

---

## 5. Wissens-/Wissenschaftsbasis (REACH-Filter)

REACH ist ein Hochschul-Center und filtert auf *wissensbasierte* Gründungen.
Die Wissensbasis von Who2Be ist **angewandte Technologie- und
Engineering-Expertise in einem sehr jungen Feld**, nicht ein Forschungspatent:

- **Emerging-Standard-Kompetenz (MCP).** Das Model Context Protocol ist ein
  erst 2024/2025 entstandener offener Standard. Ein produktionsreifer,
  OAuth-2.1-abgesicherter Remote-MCP-Connector zu bauen, ist state-of-the-art
  und wird kaum von Standardsoftware abgedeckt — das ist echtes Spezialwissen.
- **Context-/Prompt-Engineering als Disziplin.** Personas, Playbooks, Modi,
  Applied-vs-Triggered-Ladestrategien, Composite-Orchestrierung, Token-Budget —
  hier steckt konzeptionelle Arbeit, wie man Agenten-Kontext *strukturiert und
  wiederverwendbar* macht. Das ist die inhaltliche Substanz.
- **Software-Engineering-Tiefe.** Saubere Schichtenarchitektur (Clean
  Architecture / modularer Monolith), Versionierungs-Datenmodell, Mandantenfähigkeit
  mit RBAC, Row-Level-Security, OAuth-2.1-Authorization-Server, ~90 % Testabdeckung,
  Security- und Compliance-Bausteine (DSGVO/C5). Das belegt die Fähigkeit,
  aus einer Idee ein tragfähiges Produkt zu bauen.
- **Sicherheits-/Compliance-Fundament.** Zero-Trust-Owner-Prüfung, gehashte
  Tokens, Rate-Limits, Audit-Journale, MFA, verschlüsselte Off-Site-Backups —
  Anschlussfähig an regulierte Kunden.

**[BITTE ERGÄNZEN]** — falls vorhanden, hier die *persönliche* Wissensbasis
andocken: einschlägiges Studium/Fachgebiet, Forschungsnähe (z. B. NLP/KI/SE an
der Hochschule), relevante frühere Projekte/Publikationen. Das stärkt den
REACH-Filter erheblich (siehe Punkt 9 und 12).

---

## 6. Skalierbarkeit — 10× Kunden ohne 10× Kosten?

**Ja — es ist ein Softwareprodukt, kein Dienstleistungsgeschäft.**

- **Grenzkosten pro zusätzlichem Kunden sind niedrig.** Die Cloud-Edition ist
  mandantenfähig (`Organisation → Workspace`) — neue Kunden bedeuten primär
  Rechen-/Speicherlast, keine proportionale Personal-Skalierung.
- **Zwei Vertriebswege aus einer Codebasis.** Cloud-SaaS (nutzungsbasiert,
  Billing über das isolierte `who2be-billing`-Paket vorbereitet) und
  On-Prem-Lizenz (Kunde hostet selbst — noch geringere Betriebslast für uns).
- **Self-Service-fähig.** Onboarding per Magic-Link-Einladung, Ein-Klick-
  MCP-Connector — kein zwingender manueller Setup-Aufwand pro Kunde.
- **Automatisierte Qualität.** ~1.000 Tests, ~90 % Coverage, CI-Gates,
  Coverage-Ratchet — das hält die Wartungskosten pro Feature niedrig und die
  Skalierung technisch beherrschbar.

Es ist damit klar auf der **skalierbaren Produkt-Seite**, nicht auf der
Stunden-gegen-Geld-Seite. (Optionales Dienstleistungs-Add-on — Setup/Support
für On-Prem-Kunden — wäre möglich, ist aber nicht der Kern.)

---

## 7. Regionsbezug

**[BITTE ERGÄNZEN]** — Wo wohnst du, wo willst du gründen?

> Kontext: REACH EUREGIO Start-up Center ist das Gründungszentrum der
> Universität und FH Münster (Region Münster / EUREGIO). Für die Bewerbung ist
> ein Bezug zu Münster / zur Region hilfreich. Bitte hier eintragen: aktueller
> Wohnort, geplanter Gründungsstandort, ggf. Verbindung zu Münster/EUREGIO.

---

## 8. Reifegrad

**Weit fortgeschritten — lauffähiges, funktionsreiches Produkt.** Das lässt sich
am Code belegen (nicht behauptet):

- **Vollständige Full-Stack-Anwendung** ist implementiert und getestet:
  FastAPI-Backend, MCP-Server, React-Web-UI, geteilte Datenmodelle.
- **Phasen 0–3 abgeschlossen** (Tenancy, Status-Workflow + Dashboard,
  Ressourcen-Editor, Multi-User-RBAC, MCP Read-/Write-Tools, i18n).
- **Fortgeschrittene Features live im Code:** OAuth-2.1-Remote-MCP-Connector,
  Suche, Feedback-Flywheel, feingranulare Agenten-Rechte, Composite-Playbooks,
  MFA, OSS-Lizenz-Gates, Cloud-/On-Prem-Build-Trennung.
- **Qualitäts-Nachweis:** ~1.000 grüne Tests, ~90 % Backend-Coverage,
  Web-Coverage über Floor, Security-Findings der Phasen 1+2 geschlossen.
- **Deployment vorbereitet:** Hetzner-Deploy (Caddy, self-hosted Supabase),
  verschlüsselte Backups, Observability (Prometheus/Grafana).

**Einordnung:** Das ist **jenseits von Prototyp** — ein technisch belastbarer,
nahezu produktionsreifer MVP+. Was noch offen ist, ist eher Go-to-Market als
Technik: CI-/Billing-Klärung, Public-Switch des Repos, erste echte Kunden.

**[BITTE ERGÄNZEN]** — Der einzige Reifegrad-Aspekt, den der Code nicht
beantwortet: **Hast du schon mit potenziellen Kunden gesprochen?** (Interviews,
Pilot-Interessenten, Wartelisten, Design-Partner?) Das ist für Förderer sehr
wichtig — bitte hier ehrlich den Stand eintragen.

---

## 9. Du selbst — Hochschulbezug

**[BITTE ERGÄNZEN]** — entscheidet über Förderfähigkeit (z. B. EXIST).

> Bitte eintragen:
> - Studium/Abschluss (Fachrichtung), aktueller Status (immatrikuliert /
>   Absolvent:in — falls Absolvent:in: **Abschlussjahr**, da EXIST eine Frist ab
>   Exmatrikulation hat, aktuell i. d. R. bis zu 5 Jahre).
> - Welche Hochschule (Uni Münster / FH Münster / andere)?
> - Ggf. Bezug zu einem Lehrstuhl / Institut, der die Gründung mentoriert
>   (EXIST verlangt eine Hochschul-Anbindung als Gastgeber).

---

## 10. Team & Zeit

**[BITTE ERGÄNZEN]** — Allein oder im Team? Vollzeit oder neben dem Job?

> Bitte eintragen:
> - Anzahl Gründer:innen und ihre Rollen (Technik / Business / Vertrieb).
>   Förderer wie EXIST bevorzugen i. d. R. Teams (idealerweise mit
>   kaufmännischer + technischer Abdeckung).
> - Zeitliche Verfügbarkeit (Vollzeit angestrebt? aktuell nebenberuflich /
>   im Studium?).
> - Falls Solo: Plan, wie fehlende Kompetenzen (z. B. Vertrieb/Business) ergänzt
>   werden.

---

## 11. Geschäftsmodell-Idee (optional)

Aus der Produkt-Struktur ergeben sich zwei komplementäre Erlösströme, beide
bereits technisch vorbereitet:

- **Cloud-SaaS-Abo (B2B).** Gehostete, mandantenfähige Version;
  nutzungs-/sitzplatzbasierte Tarife. Das Billing-Paket (`who2be-billing`,
  Mollie-Checkout/-Webhooks, Tarif-Logik) ist angelegt und build-isoliert.
  Editionen/Entitlements (Tarif-Rechte) sind als eigenes Konzept modelliert.
- **On-Prem-Lizenz (B2B).** Für datenschutz-/compliance-getriebene Kunden, die
  selbst hosten. Lizenzmodell: **FSL-1.1** (Functional Source License) — frei für
  interne Nutzung, kein konkurrierendes Hosting; jedes Release wird 2 Jahre nach
  Veröffentlichung automatisch Apache-2.0. Kommerzielle Enterprise-Lizenz auf
  Anfrage. On-Prem-Entitlements entstehen aus einem signierten Lizenzschlüssel.

Mögliche Ergänzungen (nicht Kern): Setup-/Support-Pakete für On-Prem,
Premium-Feature-Stufen (Editionen-Gates existieren bereits als Mechanik).

**Kern-Logik:** Freemium/Open-Core-artig — offener Kern schafft Reichweite und
Vertrauen, kommerzielle Editionen (Cloud-Betrieb + Enterprise-Lizenz + Premium-
Features) monetarisieren die Teams, für die Agenten-Konfiguration
geschäftskritisch wird.

---

## 12. Warum du

**[BITTE ERGÄNZEN]** — Was qualifiziert dich für genau dieses Problem?

> Der Code beweist bereits eine sehr hohe technische Umsetzungsstärke (ein:e
> Einzelne:r oder ein kleines Team hat ein architektonisch sauberes,
> sicherheits- und compliance-bewusstes Full-Stack-Produkt mit ~90 %
> Testabdeckung gebaut). Das ist ein starkes „Warum du"-Argument. Bitte
> persönlich unterfüttern:
> - Fachlicher Hintergrund (KI/Software/…), einschlägige Erfahrung.
> - Eigener „Schmerz" mit dem Problem (hast du Who2Be gebaut, weil du selbst
>   Agenten-Prompts in Notion verwaltet und darunter gelitten hast? → sehr
>   glaubwürdige Founder-Market-Fit-Story).
> - Was dich antreibt / warum gerade jetzt (MCP-Standard entsteht *jetzt* —
>   Timing-Argument).

---

## Offene Punkte, die nur du beantworten kannst

Für eine vollständige Bewerbung fehlen mir noch: **7** (Region/Standort),
**8** (Kundengespräche stattgefunden?), **9** (Hochschule/Studium/Abschlussjahr),
**10** (Team & Zeit), **12** (persönliches „Warum du"). Trag sie an den
markierten Stellen ein oder gib sie mir, dann fülle ich sie ein und schärfe das
Dossier.

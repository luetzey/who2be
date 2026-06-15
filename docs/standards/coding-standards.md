# Coding-Standards

Geprüft von der Makro- zur Mikroebene — alle Ebenen gelten gleichzeitig und
vollständig. Repo-spezifische Konkretisierung: [`../../CLAUDE.md`](../../CLAUDE.md)
§Code-Style + die Skills `.claude/skills/python-conventions` und
`react-conventions`.

## 1. Architektur (Makroebene)

- **Separation of Concerns:** Geschäftslogik (Policies) strikt von technischen
  Details (DB, UI, Framework) isolieren.
- **Clean Architecture:** konzentrische Schichten, Abhängigkeiten verlaufen von
  außen nach innen. Kern = Entities + Use Cases, entkoppelt von Frameworks/Treibern.
- **Modularität:** unabhängige, austauschbare Komponenten.
- **Entscheidungsstrategie:** mit einem modularen Monolithen starten; erst bei
  echtem Bedarf (Skalierung) zu Microservices wechseln — keine Premature
  Distribution.
- **ADR-Praxis:** tragende Architektur-Entscheidungen als ADR im Repo festhalten
  (Warum, Alternativen, Konsequenzen) → [`../adr/`](../adr/).

> **Im Repo:** Modularer Monolith (ADR-0001), geschichtete API (ADR-0002:
> Router → Service → Repository), asyncpg-DB-Zugriff (ADR-0003), geteilte Models
> in `packages/models/` (nicht duplizieren).

## 2. Design-Prinzipien (Komponenten-Ebene)

- **SOLID** — v.a. Single Responsibility (eine Aufgabe pro Komponente) und
  Dependency Inversion (von Abstraktionen abhängen, nicht von Implementierungen).
- **KISS** — unnötige Komplexität vermeiden.
- **YAGNI** — keine Features auf Vorrat.
- **DRY** — Logik einmal schreiben und wiederverwenden.
- **Design Patterns** — bewährte Muster nur, wo sie ein echtes Problem lösen.

## 3. Clean-Code (Zeilenebene)

- **Aussagekräftige Namen:** offenbaren den Zweck ohne Zusatz-Kommentar.
- **Kleine Funktionen:** eine Funktion, eine Aufgabe.
- **Sparsame Kommentare:** erklären das *Warum*, nicht das *Was*.
- **Boy Scout Rule:** Code etwas besser hinterlassen, als man ihn vorfand.
- **Sprach-Styleguides folgen** (PEP 8 etc.). Repo-Konkretisierung: ruff
  `line-length = 100`, mypy `strict`, Type-Hints Pflicht, kein blankes `except:`;
  TypeScript `strict`, kein `any` ohne Begründung, funktionale Komponenten + Hooks.

## Anti-Patterns

- Geschäftslogik mit DB-/UI-/Framework-Details vermischen; Abhängigkeiten von
  innen nach außen; Microservices ohne Skalierungsbedarf; Architektur ohne ADR.
- God-Class / mehrere Verantwortlichkeiten; Abhängigkeit von konkreten
  Implementierungen statt Abstraktionen; spekulative Generik; Copy-Paste-Logik;
  Pattern um des Patterns willen.
- Kryptische Namen, die Kommentare brauchen; lange Multi-Aufgaben-Funktionen;
  „Was"-Kommentare; Repo-Styleguide ignorieren.

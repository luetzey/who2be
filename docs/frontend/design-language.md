# Frontend Designsprache — "Warm Citrus"

> Living document. Stand: 2026-05-27 · Phase D1 (Tokens) etabliert,
> D2–D5 (Primitives, Pages, Motion) folgen. Plan-Ablage:
> [`.claude/plans/erarbeite-eine-konkrete-designsprache-shiny-lollipop.md`](/.claude/plans/erarbeite-eine-konkrete-designsprache-shiny-lollipop.md).

Diese Datei ist die **verbindliche Designsprache** der Who2Be-Web-UI
(`apps/web/`). Sie konkretisiert, wie die in [`architecture.md`](./architecture.md)
beschriebene Architektur aussieht und sich verhaelt. Sie ist fuer die Web-UI
die verbindliche Quelle (siehe `CLAUDE.md` §Frontend-Standards).

## 1. Designphilosophie

**Profil:** Hybrid aus macOS-HIG (Admin-App) und Apple-Marketing-Touch
(Auth/Brand-Momente).

- **Admin-Pages** (Personae, Playbooks, Tokens, Detail/New) folgen HIG:
  dichte Surfaces, klare Hierarchie, dezente Tinten, funktional vor
  emotional.
- **Marketing-Pages** (heute nur `LoginPage`) duerfen einen Hero-Moment:
  groessere Headlines, weniger Chrome, mehr Whitespace, Shadow-getragene
  Surface ohne Border.

**Brand-Akzent: warmes Orange** (`Warm Citrus`) — ein eigener
Brand-Move, nicht der Apple-System-Blau-Default. Spielraum fuer Identitaet,
ohne Apple-Konventionen aufzugeben.

**Voice & Tone:** sachlich, knapp, in Du-Form, deutsch mit
Volltext-Umlauten. Kein "wir-machen-jetzt"-Marketing-Geschwurbel, keine
ausgedachten Aufzaehlungs-Adjektive ("blitzschnell", "innovativ").
Hilfetexte beantworten WIESO, nicht WAS. Buttons in der Infinitiv-Form
("Speichern", "Anlegen", "Widerrufen"), nicht "Speichere".

## 2. Color-System

### 2.1 Token-Quellen

Alle Farben sind OKLCH (ADR-0014) in
[`apps/web/src/styles/globals.css`](../../apps/web/src/styles/globals.css).
**Keine `#hex`-Literale, kein `rgb()` im JSX.**

### 2.2 Brand-Tinte (warm citrus)

| Token | Light | Dark | Verwendung |
|---|---|---|---|
| `--brand` | `oklch(0.72 0.17 55)` | `oklch(0.74 0.17 55)` | Primaere CTA-Fill |
| `--brand-foreground` | `oklch(0.985 0 0)` (weiss) | `oklch(0.145 0 0)` (dunkel) | Text auf `--brand` |
| `--brand-hover` | `oklch(0.66 0.17 55)` (dunkler) | `oklch(0.80 0.16 55)` (heller) | Hover-State |

Tailwind-Klassen: `bg-brand`, `text-brand-foreground`, `hover:bg-brand-hover`.

**Anwendungsregel:** Maximal **eine** primaere `brand`-Aktion pro
Page-Surface. Mehrere `bg-brand`-Buttons auf derselben Page = Review-Reject.
Beispiele:

- `PersonasPage`: Header-CTA "Neue Persona" = brand.
- `LoginPage`: Submit "Anmelden" = brand.
- `SettingsTokensPage`: "Anlegen" in der Token-Create-Card = brand;
  "Widerrufen" / "Override entfernen" bleiben `variant="outline"`.

### 2.3 Surface-Hierarchie

Die ehemalige "Card == Background"-Identitaet im Dark-Mode ist aufgeloest:

| Token | Light | Dark | Rolle |
|---|---|---|---|
| `--background` | `oklch(1 0 0)` | `oklch(0.145 0 0)` | Page (Layer 0) |
| `--card` | `oklch(1 0 0)` | `oklch(0.18 0 0)` | Surface (Layer 1) |
| `--popover` | `oklch(1 0 0)` | `oklch(0.21 0 0)` | Floating (Layer 2) |

Im **Light Mode** uebernimmt der Shadow-Stack die Differenzierung
(Card sitzt visuell auf der Page, ohne Farb-Tinte). Im **Dark Mode**
sind drei Helligkeitsstufen wahrnehmbar (`0.145 < 0.18 < 0.21`).

### 2.4 Status-Farben

| Token | Light | Dark | Verwendung |
|---|---|---|---|
| `--destructive` | `oklch(0.577 0.245 27.325)` | `oklch(0.396 0.141 25.723)` | Error, Delete, Revoke |
| `--destructive-foreground` | `oklch(0.985 0 0)` | `oklch(0.985 0 0)` | Text auf destructive |

Erweiterungen (Success/Warning/Info) werden hinzugefuegt, **wenn** ein
echter Use-Case auftaucht — nicht prophylaktisch. Bis dahin: keine
Bunt-Tokens ad-hoc.

### 2.5 Shadow-Stack (Elevation)

| Token | Verwendung |
|---|---|
| `--shadow-card` | Cards, Datalist-Surface (Layer 1) |
| `--shadow-popover` | Dropdowns, Tooltips (Layer 2) |
| `--shadow-modal` | Dialogs, Sheets, Marketing-Card auf `LoginPage` (Layer 3) |

Tailwind-Klassen: `shadow-card`, `shadow-popover`, `shadow-modal`.
Shadows sind OKLCH-basiert (`oklch(0 0 0 / alpha)`), damit sie konsistent
ueber Light/Dark transparent durchschimmern.

## 3. Typografie

### 3.1 Font-Stack (Apple-First)

```css
--font-sans: -apple-system, BlinkMacSystemFont, "SF Pro Text",
             "SF Pro Display", system-ui, ui-sans-serif,
             "Segoe UI", sans-serif;
```

Auf macOS/iOS rendert SF Pro nativ; auf Windows/Linux greift `system-ui`
oder `Segoe UI`. Kein Web-Font-Download — null Layout-Shift.

### 3.2 Skala

| Klasse | Size / Line | Verwendung |
|---|---|---|
| `text-xs` | 0.75 / 1.0rem | Meta (Caption, Timestamps, Tag-Counter) |
| `text-sm` | 0.875 / 1.25rem | Body in dichten Surfaces (Forms, Lists) |
| `text-base` | 1.0 / 1.5rem | Default Body |
| `text-lg` | 1.125 / 1.75rem | Card-Titles, Sub-Headings |
| `text-xl` | 1.25 / 1.75rem | Section-Headings |
| `text-2xl` | 1.5 / 2rem | **H1 auf Admin-Pages** (PageHeader.title) |
| `text-3xl` | 1.875 / 2.25rem | **H1 auf Marketing-Pages** (LoginPage) |
| `text-4xl` | 2.25 / 2.5rem | Marketing-Hero (Reserve) |
| `text-5xl` | 3.0 / 1.1 | Marketing-Display (Reserve) |

`text-3xl`–`text-5xl` sind **ausschliesslich** fuer Marketing-Pages
freigegeben. Auf Admin-Pages bleibt H1 = `text-2xl`.

### 3.3 Tracking-Konvention

| Klasse | Wert | Verwendung |
|---|---|---|
| `tracking-tight` | `-0.02em` | Alle Headings ab `text-xl` (verpflichtend) |
| `tracking-normal` | `0` | Body, Lists, Forms (Default — nichts setzen) |
| `tracking-wide` | `0.06em` | Eyebrows / Uppercase-Caps (`text-xs uppercase`) |

### 3.4 Hierarchie-Muster

**Admin-Page-Header (PageHeader):**
```
<h1 class="text-2xl font-semibold tracking-tight">Personae</h1>
<p class="text-sm text-muted-foreground">Versionierte Persona-...</p>
```

**Marketing-Page-Header (LoginPage):**
```
<span class="text-xs uppercase tracking-wide text-muted-foreground">
  Who2Be
</span>
<h1 class="text-3xl font-semibold tracking-tight">Anmeldung</h1>
<p class="text-sm text-muted-foreground">Melde dich mit deinem ...</p>
```

## 4. Spacing & Layout

### 4.1 4-px-Grid

`--spacing: 0.25rem` (4px). Tailwind-Klassen multiplizieren auf der Basis.

**Erlaubte Stufen** (von [`architecture.md` §3](./architecture.md)
delegiert): `p-1, p-2, p-3, p-4, p-6, p-8, p-12, p-16`. Gleiches gilt
fuer `gap-*`. Abweichungen wie `p-[7px]` werden im Code-Review
zurueckgewiesen — bei genuinem Bedarf einen neuen Token einfuehren, nicht
inline improvisieren.

### 4.2 Container-Sizes

| Page-Typ | Container | Begruendung |
|---|---|---|
| Admin-Page | `max-w-5xl` (1024px) | Drei-Spalten-tauglich, gut lesbare Tabellen |
| Marketing-Page | `max-w-md` (LoginPage) bis `max-w-3xl` (kuenftig) | Fokussierter Lesefluss, zentriert |

[`Container`](../../apps/web/src/components/layout/Container.tsx) ist
heute `max-w-5xl` fixiert — eine `size`-Variante kommt erst bei zweitem
Use-Case (YAGNI).

### 4.3 Rhythmus

- Page-interner Vertikal-Rhythmus: `Stack gap="lg"` (gap-6 = 24px)
  zwischen Sektionen einer Admin-Page.
- Innerhalb einer Card: `gap="md"` (16px) oder `gap="sm"` (12px).
- Marketing-Pages duerfen `gap="xl"` (32px) zwischen Hero-Bloecken.

## 5. Radii

`--radius: 0.5rem` (8px) Basis. Abgeleitet:

| Token | Wert | Verwendung |
|---|---|---|
| `--radius-sm` | 4px | Inline-Code, kleine Pills |
| `--radius-md` | 6px | Buttons (`sm`, `default`), Inputs, Selects, Textareas |
| `--radius-lg` | 8px | Buttons (`lg`), kleine Surfaces |
| `--radius-xl` | 12px | Cards, Dialogs, Sheets, Datalist-Container |

**Sonderform:** Badges/Chips → `rounded-full` (Capsule).

## 6. Elevation & Materials

Cards und Dialogs werden **durch Shadow** definiert, nicht (nur) durch
Border:

| Element | Light | Dark |
|---|---|---|
| `Card` | `shadow-card`, `border-transparent` | `shadow-card`, `border-border/50` (Border erhaelt Definition auf dunkler Surface) |
| `DialogContent` | `shadow-modal`, optional Border | `shadow-modal`, Border |
| `DropdownContent` | `shadow-popover`, Border | `shadow-popover`, Border |

Glass/Vibrancy-Effekte (Backdrop-Blur, Material-Tinten) sind heute
**out-of-scope** — Performance-/Browser-Kosten zu hoch fuer eine
Admin-UI. Reserviert fuer spaeter, falls Brand-Pages dazukommen.

## 7. Motion

### 7.1 Tokens

| Token | Wert | Anwendung |
|---|---|---|
| `--duration-fast` | 120ms | Buttons, Toggles, Hover, Focus |
| `--duration-medium` | 200ms | Dropdowns, Tabs, Inputs (Border-Glow) |
| `--duration-slow` | 320ms | Dialogs, Sheets, Page-Transitions |
| `--ease-standard` | `cubic-bezier(0.2, 0, 0, 1)` | Default fuer alle Property-Transitionen |
| `--ease-emphasized` | `cubic-bezier(0.4, 0, 0.2, 1)` | Akzent-Bewegung (Dialog-Open) |
| `--ease-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Sanftes Overshoot fuer Lift/Pop |

Tailwind-Klassen: `ease-standard`, `ease-emphasized`, `ease-spring`.
Durations werden via Arbitrary-Value verwendet (`duration-[var(--duration-fast)]`).

### 7.2 Anwendungsregeln

- **Nie `transition-all`.** Immer eine **benannte** Property-Liste:
  `transition-[background-color,box-shadow]`.
- **Keine hardcoded `ms`-Werte** im JSX. Token oder nichts.
- **`prefers-reduced-motion: reduce`** wird global respektiert: in
  `globals.css` steht eine Override-Regel, die alle Animations- und
  Transition-Dauern auf 0.01ms kappt. Eigene Komponenten muessen das
  nicht einzeln pruefen.

### 7.3 Typische Motion-Patterns

| Element | Property | Duration | Easing |
|---|---|---|---|
| Button hover | `background-color` | fast | standard |
| Card hover-lift | `box-shadow, transform` | fast | spring |
| Dialog open/close | `opacity, transform` | medium | emphasized |
| Dropdown open | `opacity, transform` | fast | standard |
| Toast slide-in | `transform` | medium | spring |
| Skeleton pulse | `opacity` | n/a (Tailwind `animate-pulse`) | n/a |

## 8. Iconografie

- **Bibliothek:** [`lucide-react`](https://lucide.dev) — bleibt
  einheitliche Quelle (kein Mix mit anderen Sets).
- **Strichstaerke:** Lucide-Default (2px) — nicht aendern.
- **Groessen:** `size-4` (16px) inline, `size-5` (20px) in Buttons,
  `size-6` (24px) in PageHeader-Actions, `size-12` (48px) als
  EmptyState-Hero.
- **Farbe:** standardmaessig `text-muted-foreground` (sekundaere
  Affordance) oder `currentColor` (folgt Textfarbe in Buttons).
  **Nie** `text-brand` — die Brand-Tinte bleibt der CTA-Fill vorbehalten.

## 9. Komponenten-Anwendungsmuster

### 9.1 Button — Variants

| Variant | Wann |
|---|---|
| `brand` (D2) | DIE eine Primary-Action pro Page-Surface |
| `default` | Neutrale Secondary-Action (Form-Submit ohne CTA-Charakter) |
| `outline` | Tertiary-Action neben einer primaeren |
| `ghost` | Header/Toolbar (Logout, Theme-Toggle, Back-Link) |
| `destructive` | Loeschen, Widerrufen, Account-Delete |
| `secondary` | Selten — bei Bedarf in dichten Toolbars |
| `link` | Inline-Verweis in Body-Text |

Sizes: `sm` (h-9, kompakte Toolbar/Header) · `default` (h-10, alle
Form-CTAs) · `lg` (h-11, Marketing-Hero) · `icon` (40×40, square).

### 9.2 Card

```
<Card class="shadow-card border-transparent dark:border-border/50">
  <CardHeader><CardTitle>...</CardTitle></CardHeader>
  <CardContent>...</CardContent>
</Card>
```

(D2 verkabelt die Standard-Klassen direkt im Primitive; ab dann reicht
`<Card>...</Card>`.)

### 9.3 DataList — Row-Affordance

Klickbare Rows zeigen einen Hover-Surface auf der **gesamten Zeile**
und einen Chevron rechts:

```
<li class="flex items-center justify-between gap-3 px-4 py-3 text-sm
           hover:bg-muted/40 transition-[background-color]
           duration-[var(--duration-fast)] ease-standard">
  <Link to={...} class="flex-1 ...">{name}</Link>
  <ChevronRight class="size-4 text-muted-foreground/60" />
</li>
```

(D5 fixiert das in `DataList`; bis dahin in Pages manuell.)

### 9.4 EmptyState — Hero + CTA

Erweitert in D3 um einen `icon`-Slot:

```
<EmptyState
  icon={Users}
  title="Noch keine Personae"
  description="Lege deine erste Persona an, um Agenten zu konfigurieren."
  action={<Button variant="brand">Neue Persona</Button>}
/>
```

Wenn die Page einen Primary-CTA im Header hat, **spiegelt** der
EmptyState diesen — sonst landet der User auf einer leeren Liste ohne
sichtbaren Anker.

### 9.5 FormSection (NEU, D3)

Gruppierung in Editor-Forms, damit eine 4–10-Feld-Form nicht als
endlose Linie wirkt:

```
<FormSection
  title="Identitaet"
  description="Wie die Persona heisst und kurz beschrieben wird.">
  <NameField />
  <DescriptionField />
</FormSection>

<FormSection
  title="Verhalten"
  description="System-Prompt und Eigenschaften — diese Felder bestimmen,
               wie der Agent antwortet."
  footer="Aenderungen erzeugen eine neue Version. Alte Versionen bleiben
          erhalten.">
  <SystemPromptField />
  <TraitsField />
</FormSection>
```

Visuell: `border-t pt-6` zwischen Sektionen, `space-y-1` zwischen
Title/Description, `text-xs text-muted-foreground` fuer Footer.

### 9.6 PageHeader — Eyebrow-Slot (Marketing)

```
<PageHeader
  eyebrow="Who2Be"          // optional, nur Marketing
  title="Anmeldung"
  description="Melde dich mit deinem Supabase-Account an."
/>
```

Eyebrow rendert als `text-xs uppercase tracking-wide text-muted-foreground`
ueber dem H1; H1 wechselt auf `text-3xl tracking-tight`.

## 10. Page-Patterns

### 10.1 Admin-Page (Standard)

```
<Container>                            {/* max-w-5xl */}
  <Stack gap="lg">
    <PageHeader title="..." description="..." actions={<Button variant="brand">...</Button>} />
    <Card>...</Card>                   {/* Filter, falls vorhanden */}
    <DataList .../>                    {/* oder Cards mit FormSections */}
  </Stack>
</Container>
```

Beispiele: `PersonasPage`, `PlaybooksPage`, `SettingsTokensPage`,
`PersonaDetailPage`, `PlaybookDetailPage`.

### 10.2 Marketing-Page (Auth, Brand)

```
<main class="flex min-h-screen items-center justify-center
             bg-muted/30 px-4 py-10">
  <Card class="w-full max-w-md shadow-modal border-transparent">
    <CardHeader>
      <span class="text-xs uppercase tracking-wide text-muted-foreground">Who2Be</span>
      <CardTitle class="text-3xl tracking-tight">Anmeldung</CardTitle>
      <CardDescription>...</CardDescription>
    </CardHeader>
    <CardContent>
      <Form>...
        <Button variant="brand" class="w-full">Anmelden</Button>
      </Form>
    </CardContent>
  </Card>
</main>
```

Heute nur `LoginPage`; weitere Brand-Pages (Onboarding, Welcome) folgen
demselben Muster.

## 11. A11y-Minimum

- **Kontrast:** Brand-Tinte (`--brand` ↔ `--brand-foreground`) muss
  WCAG-AA-tauglich sein (>= 4.5:1). Werte aus §2.2 sind verifiziert
  (siehe Plan-Anhang).
- **Hit-Targets:** Buttons `size="default"` = 40px (HIG-konform ≥ 32px),
  Mobile-Hits bevorzugt 44px (`size="lg"`).
- **Fokus:** Focus-Ring bleibt `--ring` (neutral), **nicht** auf
  `--brand` umstellen. Sonst Doppelsignal (Brand-Fill + Brand-Ring).
- **Brand-Farbe nie alleinige Information:** Statt nur "rotes
  Badge = Fehler" auch ein Icon (`AlertCircle`) und/oder Text-Label.
- **Reduced-Motion:** Globale Regel in `globals.css` kollabiert alle
  Animationen auf 0.01ms. Custom-Komponenten muessen nichts extra tun.
- **Tests:** Pages bekommen einen `*.a11y.test.tsx` mit `vitest-axe`
  (Pattern existiert seit Phase 5, ADR-0016).

## 12. Wo-was-anfassen — Decision-Map

| Aenderung | Anfassen |
|---|---|
| Farbe/Schatten/Radius/Typo-Token | **nur** `apps/web/src/styles/globals.css` |
| Neue Button-Variante | `apps/web/src/components/ui/button.tsx` (cva) + Showcase in `app/catalog/showcases/button.tsx` |
| Neue Komponente | Erst pruefen, ob Variante eines Primitives reicht. Sonst nach `components/{ui,layout,data}/` plus Test plus Showcase. |
| Page-Layout | `components/layout/*` (AppShell, PageHeader, Container, Stack, Section, FormSection) — nicht in Pages duplizieren. |
| Feedback-Toast | `lib/feedback.ts` (`notify.*`). Sonner nie direkt importieren. |
| Klassen-Merge | `lib/utils.ts` (`cn`). |
| Theme-Override | `app/ThemeProvider.tsx` + `data-theme="light|dark"` auf `<html>`. |
| Microcopy | Im Page/Component-File direkt. Pflicht: Volltext-Umlaute (`ü/ö/ä/ß`). |
| Iconografie | `lucide-react`. Kein zweites Icon-Set. |

## 13. Fuer AI-Agenten — Lese- und Schreib-Regeln

Diese Sektion ist der **Vertrag** fuer jeden AI-Agenten, der UI-Code
aendert. Bei Konflikt mit einem User-Wunsch: STOPP, beim User
nachfragen, **nicht** stillschweigend umgehen.

1. **Vor jeder UI-Aenderung lesen (Phase 1: Read):** diese Datei +
   `CLAUDE.md` §Frontend-Standards + die betroffene Primitive in
   `components/ui/` + das Showcase in `app/catalog/showcases/`.
2. **Tokens nie ad-hoc:** keine `#hex`, kein `px` im JSX, keine
   `oklch()` inline, keine eigenen Schatten/Easings/Durations. Alle
   Werte leben in `apps/web/src/styles/globals.css`.
3. **Skalen respektieren:** Spacing nur in `p-{1,2,3,4,6,8,12,16}` und
   gleichen `gap-*`; Typo nur aus der Skala (§3.2); Radii nur per
   Anwendungsregel (§5). Abweichungen brauchen **Token-Aenderung + ADR**,
   nicht inline.
4. **Brand sparsam:** `variant="brand"` ist die **eine** Primary-Aktion
   pro Page-Surface. Zwei brand-Buttons nebeneinander = Reject.
   Destruktive Aktionen sind `variant="destructive"`, neutrale
   `variant="default"` oder `"outline"`.
5. **Neue Komponente?** Erst pruefen, ob ein bestehendes Primitive ueber
   `cva`-Variants oder Composition reicht. Wenn nicht: in
   `components/{ui,layout,data}/`, plus Showcase im Catalog, plus
   Vitest-Test, plus a11y-Test (wenn interaktiv).
6. **Motion nur ueber Tokens:** keine `transition-all`, keine hardcoded
   ms. `prefers-reduced-motion` darf nie umgangen werden (globale Regel
   in `globals.css` kuemmert sich darum — nicht aushebeln).
7. **Microcopy:** Deutsche **Volltext-Umlaute** (`ü/ö/ä/ß`) im
   UI-String. ASCII (`ue/oe/ae/ss`) **nur** in Code-Identifiern,
   Datei-Kommentaren und Repo-Doku (wie dieser Datei) — nicht in
   sichtbarem UI-Text.
8. **A11y-Pflicht:** Jede neue klickbare/eingebbare Komponente bekommt
   einen `*.a11y.test.tsx` (`vitest-axe`). Pages, die echte
   Daten/Forms zeigen, sowieso. Focus-Ring nie wegklassen.
9. **Verbindlichkeit:** Diese Guideline ist fuer die Web-UI die
   maßgebliche Quelle (Konsistenz mit `CLAUDE.md` §Frontend-Standards).
10. **DoD pro Aenderung:** `npm run lint && npx tsc --noEmit &&
    npm test && npm run build` (in `apps/web/`) — alle vier gruen, lokal
    verifiziert, **vor** dem Push.
11. **Bei Unsicherheit:** STOP, frag den User. Lieber eine Frage als
    ein UI-Inconsistency-PR.

---

### Versionierung

- 2026-05-27 — Initial (Phase D1 Tokens etabliert). Plan:
  [`.claude/plans/erarbeite-eine-konkrete-designsprache-shiny-lollipop.md`](/.claude/plans/erarbeite-eine-konkrete-designsprache-shiny-lollipop.md).

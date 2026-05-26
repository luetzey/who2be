# ADR-0017 — Frontend-AppShell: Route-Level `<AppLayout>` mit `<Outlet/>`

- Status: Akzeptiert
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), Frontend-Umbau Phase 0

## Kontext

Heute mountet **jede Page** den App-Shell selbst:

```tsx
// features/personas/pages/PersonaDetailPage.tsx
<AppShell onSignOut={() => void signOut()}>
  <Container>…</Container>
</AppShell>
```

Das verstoesst gegen das Frontend-Standards-Playbook auf zwei Ebenen:

- "Eine Quelle der Wahrheit pro Design-Entscheidung" — Seiten-Chrome
  wird in jeder Page einzeln entschieden.
- "UX-Kohaerenz: ein einziger App-Shell, durch den jede Seite laeuft" —
  das ist heute formal so, aber jede Page wickelt die Shell selbst.

Zusaetzlich macht es Test-Setup, Theme-Toggle-Mount und Toaster-Mount
unnoetig komplex: alles muss durch alle sieben Pages dupliziert oder via
Provider von aussen gespannt werden.

## Optionen

- **A — Route-Level `<AppLayout>` mit `<Outlet/>`.** Kanonisches
  react-router-v7-Pattern. `AppLayout` mountet `<AppShell>` und rendert
  `<Outlet/>`. Authenticated-Routes liegen darunter. Pages haben nur
  noch Inhalt — `<Container><Stack>…</Stack></Container>` o.ae. Kostet
  einmalig 1 neuer `AppLayout.tsx` + 7 Page-Edits. Test-Setup wird mit
  `renderInRoutes`-Helper konsistent zur Produktion.
- **B — HOC `withAppShell(Page)`.** Pages bleiben "Wurzeln", Shell wird
  per HOC injiziert. Hidden-Indirection, schlechter testbar; Theme-
  Toggle-Slot waere weiterhin schwierig.
- **C — IST belassen.** Verstoesst gegen Standards 1 und 6.

## Entscheidung

**Option A — Route-Level `<AppLayout>` mit `<Outlet/>`.**

Struktur ab Phase 2:

```tsx
// app/routes.tsx
<BrowserRouter>
  <SessionProvider>
    <AuthTokenProvider>
      <ThemeProvider>
        <Routes>
          <Route path="/login" element={<LoginPage/>}/>
          <Route element={<RequireAuth/>}>
            <Route element={<AppLayout/>}>
              <Route path="/" element={<PersonasPage/>}/>
              <Route path="/personas/new" element={…}/>
              …
            </Route>
          </Route>
        </Routes>
      </ThemeProvider>
    </AuthTokenProvider>
  </SessionProvider>
</BrowserRouter>
```

`AppLayout` mountet:

- `<AppShell onSignOut={…}>` (Session-Konsum hier konsolidiert)
- `<Outlet/>`
- `<Toaster/>` (Phase 3.1)
- `<RouteErrorBoundary/>` als Wrapper

`AppShell` selbst verliert die `onSignOut`-Prop nicht — sie wandert aber
in `AppLayout` und kommt nicht mehr aus jeder Page einzeln. Optional:
in Phase 6 erhaelt `AppShell` einen `actions?: ReactNode`-Slot fuer den
Theme-Toggle.

ESLint-Regel ergaenzt: `@/components/layout/AppShell` darf nur aus
`src/app/**` importiert werden. Pages importieren `AppShell` nicht mehr.

## Konsequenzen

- 1 Mount-Punkt fuer Shell + Toaster + Theme-Provider + Error-Boundary.
- Pages verlieren `useSession()`-Aufruf nur fuer `signOut`.
- Page-Tests werden via `renderInRoutes(page, { path })` gerendert →
  Outlet-DOM ist konsistent zur Produktion, vorhandene Assertions auf
  Nav-Roles bleiben greifbar.
- Lazy + Suspense (Phase 2.6) wird trivial — der Suspense-Fallback wird
  innerhalb `AppLayout` gemountet, also bleibt Nav sichtbar waehrend
  Page-Chunks laden.
- Roll-Back ist Revert von Phase 2 — Pages haetten dann wieder `AppShell`-
  Imports, aber das ist ein gut markiertes Set von 7 Files.

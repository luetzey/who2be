- Web-Tests: Die axe-Tests (`*.a11y.test.tsx`) laufen in einem eigenen
  Vitest-Projekt `a11y` mit 15 s Timeout statt der 5 s Vorgabe. Unter fremder
  CPU-Last brauchte axe über eine ganze Seite in jsdom bis zu ~7 s und riss das
  Default-Timeout (AgentDetailPage, FeedbackOverviewPage). Alle übrigen Tests
  (Projekt `unit`) behalten 5 s; Testmenge, Coverage-Gate und Skip-Budget
  bleiben unverändert.

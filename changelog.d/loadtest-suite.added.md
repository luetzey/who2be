- Belastungstest-Suite unter `loadtest/` (k6, ADR-0062 Paket A4): Szenarien
  T1–T11 für MCP-Agenten und Web-Strecken mit den vorläufigen SLOs als
  Schwellen, ein MCP-Client für Streamable HTTP, ein Seed-Skript für
  synthetische Testdaten und eine Berichtsvorlage.

  Die Skripte brechen ab, bevor ein Request rausgeht, wenn das Ziel auf
  who2be.de zeigt oder der Schalter `W2B_LOADTEST_CONFIRM` fehlt.

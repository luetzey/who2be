"""Client-Submodule des MCP-Servers (Architektur-Entscheidung 3.2, ADR-0047).

Neue Domains (WorkArea/KB/Tables) haengen ihre REST-Aufrufe als freie
Funktionen an den bestehenden `who2be_mcp.client.ApiClient` (erster
Parameter), statt `client.py` weiter wachsen zu lassen: ein Modul pro Domain
(`clients/<domain>.py`), datei-disjunkt fuer parallele Arbeitspakete
(WP8/WP9/WP19). Die Module teilen sich nur die stabilen Request-Helper des
`ApiClient` — `client.py` selbst bleibt unangetastet.
"""

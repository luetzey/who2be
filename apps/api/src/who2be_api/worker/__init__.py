"""Eingebauter Worker fuer Hintergrund-Routinen (ADR-0057).

Der Worker ist ein eigener Compose-Dienst (`who2be-worker`, gleiches Image wie
`api`) und fuehrt ausschliesslich Who2Be-eigene Wartungsroutinen aus. Die
Exklusivitaet je Lauf liegt in Postgres (`routine_run`, UNIQUE (routine,
slot)), ein Advisory-Lock verhindert Ueberlappung mit CLI-Laeufen.

Module:
- `store` — Laufprotokoll, Heartbeats, Advisory-Lock (Owner-Verbindung).
"""

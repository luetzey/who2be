"""Eingebauter Worker fuer Hintergrund-Routinen (ADR-0057).

Der Worker ist ein eigener Compose-Dienst (`who2be-worker`, gleiches Image wie
`api`) und fuehrt ausschliesslich Who2Be-eigene Wartungsroutinen aus. Die
Exklusivitaet je Lauf liegt in Postgres (`routine_run`, UNIQUE (routine,
slot)), ein Advisory-Lock verhindert Ueberlappung mit CLI-Laeufen.

Module:
- `store` — Laufprotokoll, Heartbeats, Advisory-Lock (Owner-Verbindung).
- `registry` — Anmeldung der Routinen per `@routine`.
- `schedule` — Zeitplaene, Env-Overrides, effektive Tabelle.
- `runner` — Tick-Schleife, Slot-Claim, Lock, Timeout, Nachholen.
- `cli` — Befehl `who2be-worker [run | check | list | run-once]`.
"""
